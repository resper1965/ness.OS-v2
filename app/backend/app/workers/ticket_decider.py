"""Decisor de chamados: carência, causa -> sintoma, dedup e reabertura (spec 2026-11-15).

A ingestão só grava o incidente `pending`; este ciclo (beat, 60 s) decide quem vira
chamado. Falha do GLPI num item deixa o item `pending` para o próximo ciclo.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.integrations.glpi import GLPIClient
from app.ml.analyzer import analyze_incident
from app.models import Incident, IncidentAction, PlatformParam, TicketLink
from app.services.ticket_policy import TICKET_DEFAULTS, classify, is_cause, load_rules
from app.workers import alerts
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


def _tag(inc: Incident, name: str):
    return (inc.tags or {}).get(name)


def _grace_from(inc: Incident) -> datetime:
    raw = _tag(inc, "ninf_grace_from")
    return datetime.fromisoformat(raw) if raw else inc.first_seen


async def _params(session) -> dict[str, int]:
    rows = await session.execute(
        select(PlatformParam.key, PlatformParam.value_int).where(
            PlatformParam.key.in_(TICKET_DEFAULTS)
        )
    )
    return {**TICKET_DEFAULTS, **dict(rows.all())}


async def _set_state(incident_id: int, state: str, **tags) -> None:
    async with SessionLocal() as session:
        async with session.begin():
            inc = await session.get(Incident, incident_id, with_for_update=True)
            assert inc is not None
            if _tag(inc, "ninf_ticket_state") != "pending":
                return
            inc.tags = {**inc.tags, "ninf_ticket_state": state, **tags}


def _alert_data(inc: Incident) -> dict:
    return {
        "host_id": inc.host_id,
        "host_name": inc.host_name,
        "trigger_id": inc.trigger_id,
        "trigger_name": inc.title,
        "trigger_description": inc.sanitized_description or "",
        "severity": inc.severity,
        "tags": inc.tags or {},
    }


async def _open(glpi: GLPIClient, inc: Incident, now: datetime, reopen_h: int) -> str:
    entity_id = int(_tag(inc, "ninf_entity_id"))
    key = _tag(inc, "ninf_dedup_key")
    async with SessionLocal() as session:
        link = await session.get(TicketLink, (entity_id, key))
    await glpi.change_active_entity(entity_id)
    if link and link.state == "open":
        await glpi.add_comment(
            ticket_id=link.ticket_id,
            content=f"Voltou a ocorrer às {now:%H:%M} UTC.",
            private=False,
        )
        await alerts.attach_incident(inc.id, entity_id, key, link.ticket_id)
        return "attached"
    if (
        link
        and link.state == "auto_closed"
        and link.closed_at is not None
        and link.closed_at >= now - timedelta(hours=reopen_h)
    ):
        await glpi.reopen_ticket(
            link.ticket_id, f"Problema voltou às {now:%H:%M} UTC; chamado reaberto."
        )
        async with SessionLocal() as session:
            async with session.begin():
                row = await session.get(
                    TicketLink, (entity_id, key), with_for_update=True
                )
                assert row is not None
                row.state, row.closed_at, row.source_resolved_at = "open", None, None
        await alerts.attach_incident(inc.id, entity_id, key, link.ticket_id)
        return "reopened"

    previous = link.ticket_id if link else None
    data = _alert_data(inc)
    customer = _tag(inc, "ninf_customer_name") or ""
    analysis = await analyze_incident(
        incident_data=data,
        customer_metadata={"customer_name": customer, "entity_id": entity_id},
    )
    content = alerts.build_glpi_ticket_content(data, analysis)
    if previous:
        content += f"<p><b>Chamado anterior:</b> #{int(previous)}</p>"
    # Uma reserva por geração do chamado: depois de fechado, a mesma chave abre outro.
    reservation = sha256(f"{key}:{previous or 0}".encode()).hexdigest()
    ticket_id, created = await alerts.ensure_glpi_ticket_serialized(
        glpi,
        fingerprint=reservation,
        entity_id=entity_id,
        category_id=alerts.resolve_glpi_category_id(data),
        title=f"[AIOps] {inc.title}",
        content=content,
        linked_item=await alerts.lookup_glpi_asset(inc.host_id, customer),
        urgency=alerts.glpi_urgency(inc.severity),
        lookup_first=False,
    )
    async with SessionLocal() as session:
        async with session.begin():
            row = await session.get(TicketLink, (entity_id, key), with_for_update=True)
            if row is None:
                session.add(
                    TicketLink(entity_id=entity_id, dedup_key=key, ticket_id=ticket_id)
                )
            else:
                row.ticket_id, row.state, row.occurrences = ticket_id, "open", 1
                row.closed_at = row.source_resolved_at = None
                row.last_seen = now
            db_inc = await session.get(Incident, inc.id, with_for_update=True)
            assert db_inc is not None
            db_inc.deskmanager_ticket_id = str(ticket_id)
            db_inc.tags = {**db_inc.tags, "ninf_ticket_state": "opened"}
            session.add(
                IncidentAction(
                    incident_id=inc.id,
                    actor_source="glpi",
                    action="ticket_created" if created else "ticket_reused",
                    previous_status=db_inc.status,
                    new_status=db_inc.status,
                    previous_assignee_id=db_inc.assigned_user_id,
                    new_assignee_id=db_inc.assigned_user_id,
                    note=f"ticket={ticket_id} entity={entity_id}",
                )
            )
    if settings.alert_notifications_enabled and (
        analysis.urgency in ("HIGH", "CRITICAL") or analysis.isolation_required
    ):
        try:
            from app.integrations.webpush import notify_tenant_stakeholders

            await notify_tenant_stakeholders(
                tenant_id=customer.lower().strip(),
                title=f"Alerta Crítico: {inc.title}",
                body=f"Host {inc.host_name} precisa de atenção. "
                f"IA sugere: {analysis.executive_action_plan[:100]}...",
                incident_id=str(inc.id),
                fingerprint=inc.fingerprint,
                severity=analysis.urgency.lower(),
            )
        except Exception as exc:
            logger.error("Web Push falhou: %s", type(exc).__name__)
    return "opened"


async def _notify_symptoms(glpi: GLPIClient) -> int:
    """Um comentário por causa com chamado listando os sintomas ainda não citados."""
    async with SessionLocal() as session:
        symptoms = (
            (
                await session.execute(
                    select(Incident).where(
                        Incident.tags["ninf_ticket_state"].astext == "symptom",
                        Incident.tags["ninf_notified"].astext.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        by_cause = defaultdict(list)
        for s in symptoms:
            by_cause[int(_tag(s, "ninf_cause_incident_id"))].append(s)
        causes = {
            c.id: c
            for c in (
                await session.execute(
                    select(Incident).where(Incident.id.in_(list(by_cause)))
                )
            ).scalars()
            if c.deskmanager_ticket_id
        }
    sent = 0
    for cause_id, items in by_cause.items():
        cause = causes.get(cause_id)
        if cause is None:
            continue
        lines = "".join(
            f"<li>{escape(s.host_name)}: {escape(s.title)}</li>" for s in items
        )
        try:
            await glpi.change_active_entity(int(_tag(cause, "ninf_entity_id")))
            await glpi.add_comment(
                ticket_id=int(cause.deskmanager_ticket_id or 0),
                content=f"<p>Alertas afetados por esta causa:</p><ul>{lines}</ul>",
                private=False,
            )
        except Exception as exc:
            logger.error("Comentário de sintomas falhou: %s", type(exc).__name__)
            continue
        async with SessionLocal() as session:
            async with session.begin():
                for s in items:
                    row = await session.get(Incident, s.id, with_for_update=True)
                    assert row is not None
                    row.tags = {**row.tags, "ninf_notified": "1"}
        sent += 1
    return sent


async def decide(now: datetime) -> dict[str, int]:
    stats: dict[str, int] = defaultdict(int)
    async with SessionLocal() as session:
        rules = await load_rules(session)
        params = await _params(session)
        problem = Incident.tags["ninf_zabbix_status"].astext == "problem"
        pending = (
            (
                await session.execute(
                    select(Incident)
                    .where(Incident.tags["ninf_ticket_state"].astext == "pending")
                    .where(problem)
                    .order_by(Incident.first_seen, Incident.id)
                )
            )
            .scalars()
            .all()
        )
        with_site = (
            (
                await session.execute(
                    select(Incident).where(
                        problem, Incident.tags["ninf_site"].astext.isnot(None)
                    )
                )
            )
            .scalars()
            .all()
        )
    grace = timedelta(minutes=params["ticket_grace_minutes"])
    lead = timedelta(minutes=params["ticket_symptom_lead_minutes"])
    active_causes = [c for c in with_site if is_cause(c.title, rules)]

    glpi = GLPIClient()
    try:
        causes = [i for i in pending if is_cause(i.title, rules)]
        rest = [i for i in pending if not is_cause(i.title, rules)]
        for inc in causes + rest:
            cause = None
            if inc in rest and _tag(inc, "ninf_site"):
                cause = next(
                    (
                        c
                        for c in active_causes
                        if c.id != inc.id
                        and _tag(c, "ninf_entity_id") == _tag(inc, "ninf_entity_id")
                        and _tag(c, "ninf_site") == _tag(inc, "ninf_site")
                        and c.first_seen <= inc.first_seen + lead
                    ),
                    None,
                )
            if cause is not None:
                await _set_state(inc.id, "symptom", ninf_cause_incident_id=cause.id)
                stats["symptom"] += 1
                continue
            if now - _grace_from(inc) < grace:
                stats["waiting"] += 1
                continue
            if inc in rest and classify(inc.title, inc.severity, rules) == "panel":
                await _set_state(inc.id, "panel")
                stats["panel"] += 1
                continue
            try:
                if not glpi.session_token:
                    await glpi.init_session()
                stats[await _open(glpi, inc, now, params["ticket_reopen_hours"])] += 1
            except Exception as exc:
                logger.error(
                    "Chamado do incidente %s adiado: %s", inc.id, type(exc).__name__
                )
                stats["failed"] += 1
        if active_causes:
            try:
                if not glpi.session_token:
                    await glpi.init_session()
                stats["symptom_comments"] = await _notify_symptoms(glpi)
            except Exception as exc:
                logger.error("Sintomas não comentados: %s", type(exc).__name__)
    finally:
        if glpi.session_token:
            await glpi.kill_session()
    return dict(stats)


@celery_app.task(name="app.workers.ticket_decider.decide_tickets")
def decide_tickets() -> dict[str, int]:
    redis = alerts._get_sync_redis()
    try:
        # Um ciclo por vez: ciclo lento não pode abrir o mesmo chamado em paralelo.
        if not redis.set("ninf:ticket_decider", "1", ex=300, nx=True):
            return {"skipped": 1}
        try:
            return asyncio.run(decide(datetime.now(timezone.utc)))
        finally:
            redis.delete("ninf:ticket_decider")
    finally:
        redis.close()
