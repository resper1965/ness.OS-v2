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
from sqlalchemy.sql import func

from app.config import get_settings
from app.database import SessionLocal
from app.integrations.glpi import GLPIClient
from app.ml.analyzer import PROMPT_VERSION_NOC, analyze_incident, source_urgency
from app.models import Incident, IncidentAction, PlatformParam, TicketLink
from app.services.ai_decisions import record_ai_decision
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


async def _set_tag(incident_id: int, **tags) -> None:
    async with SessionLocal() as session:
        async with session.begin():
            inc = await session.get(Incident, incident_id, with_for_update=True)
            if inc is not None:
                inc.tags = {**(inc.tags or {}), **tags}


async def _retry_cross_links(glpi: GLPIClient, now: datetime, window_min: int) -> None:
    """Uma segunda tentativa da ligação NOC/SOC que falhou; depois disso desiste."""
    async with SessionLocal() as session:
        todo = (
            (
                await session.execute(
                    select(Incident).where(
                        Incident.tags["ninf_cross_link_retry"].astext == "true"
                    )
                )
            )
            .scalars()
            .all()
        )
    if todo and not glpi.session_token:
        await glpi.init_session()
    for inc in todo:
        await _set_tag(inc.id, ninf_cross_link_retry=False)
        try:
            await glpi.change_active_entity(int(_tag(inc, "ninf_entity_id")))
            await _cross_link(
                glpi, inc, int(inc.deskmanager_ticket_id or 0), now, window_min
            )
        except Exception as exc:
            logger.error(
                "Nova ligação NOC/SOC do incidente %s falhou: %s",
                inc.id,
                type(exc).__name__,
            )


async def _set_state(incident_id: int, state: str, **tags) -> None:
    async with SessionLocal() as session:
        async with session.begin():
            inc = await session.get(Incident, incident_id, with_for_update=True)
            assert inc is not None
            if _tag(inc, "ninf_ticket_state") != "pending":
                return
            inc.tags = {**inc.tags, "ninf_ticket_state": state, **tags}


def _still_pending(inc: Incident) -> bool:
    return (
        _tag(inc, "ninf_ticket_state") == "pending"
        and (_tag(inc, "ninf_zabbix_status") or "problem") == "problem"
    )


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


async def _cross_link(
    glpi: GLPIClient, inc: Incident, ticket_id: int, now: datetime, window_min: int
) -> None:
    """Liga o chamado novo ao do outro ramo (NOC/SOC) do mesmo cliente e máquina.

    A máquina é `host_name`; sem ela, o site. Só olha chamados abertos há até
    `window_min` minutos. Mesmo ramo nunca liga: a dedup já cuida.
    """
    # ponytail: só enxerga chamado aberto pelo decisor na janela (tag opened_at); chamado
    # reaberto não entra. Upgrade path: derivar da TicketLink aberta + reopen time.
    entity_id, branch = _tag(inc, "ninf_entity_id"), _tag(inc, "ninf_branch") or "noc"
    since = (now - timedelta(minutes=window_min)).isoformat()
    async with SessionLocal() as session:
        others = (
            (
                await session.execute(
                    select(Incident).where(
                        Incident.id != inc.id,
                        Incident.status.not_in(("resolved", "closed")),
                        Incident.tags["ninf_ticket_state"].astext == "opened",
                        Incident.tags["ninf_entity_id"].astext == str(entity_id),
                        Incident.tags["ninf_ticket_opened_at"].astext >= since,
                        Incident.deskmanager_ticket_id.isnot(None),
                    )
                )
            )
            .scalars()
            .all()
        )
    same_machine = {
        int(o.deskmanager_ticket_id or 0)
        for o in others
        if (_tag(o, "ninf_branch") or "noc") != branch
        and (
            o.host_name.lower() == inc.host_name.lower()
            if inc.host_name
            else _tag(o, "ninf_site") == _tag(inc, "ninf_site")
        )
        and o.deskmanager_ticket_id != str(ticket_id)
    }
    same_machine.discard(0)
    for other in same_machine:
        await glpi.link_tickets(ticket_id, other)
        for a, b in ((ticket_id, other), (other, ticket_id)):
            await glpi.add_comment(
                ticket_id=a,
                content=f"Chamado relacionado do outro ramo (NOC/SOC): #{b}.",
                private=False,
            )


async def _open(
    glpi: GLPIClient,
    inc: Incident,
    now: datetime,
    reopen_h: int,
    cross_min: int = TICKET_DEFAULTS["ticket_cross_link_minutes"],
) -> str:
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

    async with SessionLocal() as session:
        fresh = await session.get(Incident, inc.id)
    if fresh is None or not _still_pending(fresh):
        return "skipped"  # recuperado ou decidido enquanto o ciclo rodava

    previous = link.ticket_id if link else None
    data = _alert_data(inc)
    customer = _tag(inc, "ninf_customer_name") or ""
    soc = _tag(inc, "ninf_branch") == "soc"
    if soc:
        # Ramo SOC: a triagem já rodou na ingestão; sem segunda chamada ao modelo.
        analysis = None
        content = (
            "<h2>Alerta de segurança</h2>"
            f"<p><b>Host:</b> {escape(inc.host_name)}</p>"
            f"<p><b>Resumo:</b> {escape(inc.sanitized_description or '')}</p>"
        )
    else:
        analysis = await analyze_incident(
            incident_data=data,
            customer_metadata={"customer_name": customer, "entity_id": entity_id},
            skip=await alerts._ai_skip(customer) if settings.llm_api_key else None,
        )
        content = alerts.build_glpi_ticket_content(data, analysis)
    if previous:
        content += f"<p><b>Chamado anterior:</b> #{int(previous)}</p>"
    hub = f"{settings.dashboard_base_url}/?view=incidents&id={inc.id}"
    content += f'<p><a href="{escape(hub)}">ver no ness.OS</a></p>'
    # Uma reserva por geração do chamado: depois de fechado, a mesma chave abre outro.
    reservation = sha256(f"{key}:{previous or 0}".encode()).hexdigest()
    ticket_id, created = await alerts.ensure_glpi_ticket_serialized(
        glpi,
        fingerprint=reservation,
        entity_id=entity_id,
        category_id=alerts.resolve_glpi_category_id(data),
        title=f"[AIOps] {inc.title}",
        content=content,
        # host_id do ramo SOC é id de agente Wazuh: não casa com ativo do Zabbix
        linked_item=(
            None if soc else await alerts.lookup_glpi_asset(inc.host_id, customer)
        ),
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
            db_inc.tags = {
                **db_inc.tags,
                "ninf_ticket_state": "opened",
                "ninf_ticket_opened_at": now.isoformat(),
            }
            recovered = _tag(db_inc, "ninf_zabbix_status") == "resolved"
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
            call = analysis._call if analysis else None
            if analysis is not None and call is not None:
                await record_ai_decision(
                    session,
                    kind="incident_analysis",
                    customer_id=customer.lower().strip(),
                    source_ref=f"{inc.fingerprint}:{_tag(inc, 'ninf_zabbix_event_id') or ''}",
                    call=call,
                    prompt_version=PROMPT_VERSION_NOC,
                    request=analysis._request,
                    response=analysis.model_dump() if call.outcome == "ok" else {},
                    rule_value=source_urgency(data),
                    model_value=(
                        None
                        if call.outcome != "ok"
                        else (
                            "ISOLATE"
                            if analysis.isolation_required
                            else analysis.urgency
                        )
                    ),
                    incident_id=inc.id,
                    ticket_id=str(ticket_id),
                )
    try:
        await _cross_link(glpi, inc, ticket_id, now, cross_min)
    except Exception as exc:  # o chamado já existe; a ligação não pode derrubá-lo
        logger.error(
            "Ligação NOC/SOC do incidente %s falhou: %s", inc.id, type(exc).__name__
        )
        await _set_tag(inc.id, ninf_cross_link_retry=True)
    if recovered:
        # A recuperação chegou durante a criação e não viu o vínculo: fecha agora.
        await alerts.close_ticket_if_recovered(entity_id, key, now)
    # Push pela severidade da origem (a IA só opina), como na ingestão antiga.
    if settings.alert_notifications_enabled and source_urgency(data) in (
        "HIGH",
        "CRITICAL",
    ):
        try:
            from app.integrations.webpush import notify_tenant_stakeholders

            await notify_tenant_stakeholders(
                tenant_id=customer.lower().strip(),
                title=f"Alerta Crítico: {inc.title}",
                body=(
                    f"Host {inc.host_name} precisa de atenção. "
                    f"IA sugere: {analysis.executive_action_plan[:100]}..."
                    if analysis
                    else f"Host {inc.host_name} precisa de atenção."
                ),
                incident_id=str(inc.id),
                fingerprint=inc.fingerprint,
                severity=source_urgency(data).lower(),
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
            # Sev 4–5 sempre abre chamado próprio, mesmo com causa ativa no site.
            if inc in rest and _tag(inc, "ninf_site") and inc.severity < 4:
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
                stats[
                    await _open(
                        glpi,
                        inc,
                        now,
                        params["ticket_reopen_hours"],
                        params["ticket_cross_link_minutes"],
                    )
                ] += 1
            except Exception as exc:
                logger.error(
                    "Chamado do incidente %s adiado: %s", inc.id, type(exc).__name__
                )
                stats["failed"] += 1
        try:
            await _retry_cross_links(glpi, now, params["ticket_cross_link_minutes"])
        except Exception as exc:
            logger.error("Reenvio de ligações falhou: %s", type(exc).__name__)
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
    try:
        stats["volume_warn"] = await _check_volume(
            now, params["incident_volume_warn_threshold"]
        )
    except Exception:
        logger.exception("Checagem de volume falhou")
    return dict(stats)


async def _check_volume(now: datetime, threshold: int) -> int:
    """Notifica o plantão se o volume de incidentes em 24h passar do limiar.

    Um aviso por cliente + global por ciclo de 6h (dedup simples via Redis).
    """
    from app.integrations.webpush import notify_tenant_stakeholders

    redis = alerts._get_sync_redis()
    try:
        key = f"ninf:volume_warn:{now.strftime('%Y-%m-%d-%H')}"
        if not redis.set(key, "1", ex=43200, nx=True):
            return 0  # já avisou neste ciclo de 6h
    finally:
        redis.close()

    async with SessionLocal() as session:
        since = now - timedelta(hours=24)
        # global
        total = await session.scalar(
            select(func.count(Incident.id)).where(Incident.first_seen >= since)
        )
        if total and total >= threshold:
            try:
                await notify_tenant_stakeholders(
                    tenant_id="",
                    title=f"Volume alto: {total} incidentes em 24h",
                    body=f"Limiar: {threshold}. Verifique o painel.",
                    severity="warning",
                )
            except Exception:
                logger.exception("Push de volume global falhou")
            return total or 0
    return 0


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
