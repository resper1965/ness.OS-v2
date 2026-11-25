import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from hashlib import blake2b
from html import escape
from typing import Any, Dict
from uuid import uuid4

from celery.exceptions import Retry
from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.database import SessionLocal
from app.integrations.glpi import GLPIClient, GLPIPermanentError, GLPITransientError
from app.integrations.loki import LokiClient
from app.integrations.zabbix import ZabbixClient
from app.models import (
    Asset,
    Customer,
    HostgroupRule,
    Incident,
    IncidentAction,
    TicketLink,
)
from app.services.ai_gate import ai_gate
from app.services.customers import AmbiguousCustomer, resolve_active_customer
from app.services.ticket_policy import dedup_key, site_from_hostgroups
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_sync_redis() -> Redis:
    """Redis síncrono para o worker Celery."""
    return Redis.from_url(settings.redis_url, decode_responses=True)


def resolve_customer_name(h_name: str, tags_dict: dict[str, str]) -> str:
    for k in (
        "cliente",
        "client",
        "customer",
        "tenant",
        "Cliente",
        "Client",
        "Customer",
        "Tenant",
    ):
        if tags_dict and k in tags_dict and tags_dict[k]:
            return tags_dict[k]
    if "-" in h_name:
        parts = h_name.split("-")
        if len(parts) > 1:
            first = parts[0]
            if first.lower() not in (
                "wan",
                "lan",
                "srv",
                "web",
                "db",
                "app",
                "fw",
                "vpn",
                "core",
                "test",
            ):
                return first.upper()
    return "Outros"


def glpi_urgency(severity: Any = None) -> int:
    """Urgência = impacto do GLPI (1-5) pela severidade Zabbix; desconhecido fica em 3.

    Ausente, inválido, 0 (não classificado), fora de faixa ou bool nunca rebaixam
    (regra 7 da política SOC).
    ponytail: só Zabbix; o mapeamento Wazuh (nível/score) entra junto com o
    chamador quando o fluxo Wazuh criar ticket. Sem SLA/grupo/origem (T08).
    """
    if isinstance(severity, bool) or not isinstance(severity, int):
        return 3
    return severity if 1 <= severity <= 5 else 3


def resolve_glpi_category_id(alert_data: Dict[str, Any]) -> int:
    """Resolve o ID da categoria do GLPI com base nos dados do alerta.

    Se for um alerta de segurança (SOC, SIEM, Wazuh, etc.), retorna settings.glpi_security_category_id.
    Caso contrário (NOC, Zabbix infra), retorna settings.glpi_infra_category_id.
    """
    trigger_name = alert_data.get("trigger_name", "").lower()
    tags = alert_data.get("tags", {})
    if tags.get("ninf_branch") == "soc":
        return settings.glpi_security_category_id

    # 1. Verificar se o assunto do gatilho contém termos de segurança
    security_keywords = [
        "secops",
        "soc",
        "wazuh",
        "siem",
        "seguranca",
        "segurança",
        "firewall",
        "intrusao",
        "intrusão",
        "malware",
        "virus",
        "phishing",
        "brute force",
        "bruteforce",
        "scan",
    ]
    if any(kw in trigger_name for kw in security_keywords):
        return settings.glpi_security_category_id

    # 2. Verificar chaves e valores das tags
    if tags:
        for k, v in tags.items():
            k_lower = str(k).lower()
            v_lower = str(v).lower()
            if any(
                kw in k_lower or kw in v_lower
                for kw in [
                    "soc",
                    "wazuh",
                    "siem",
                    "security",
                    "seguranca",
                    "segurança",
                ]
            ):
                return settings.glpi_security_category_id

    return settings.glpi_infra_category_id


async def customer_from_hostgroups(
    session: Any, groups: list[dict[str, str]]
) -> str | None:
    """Nome canônico do cliente dos grupos `[Cliente]`; ambiguidade levanta ValueError."""
    rules = list(
        (
            await session.execute(
                select(HostgroupRule).order_by(HostgroupRule.priority, HostgroupRule.id)
            )
        ).scalars()
    )
    by_name: dict[str, list[int]] = {}
    for rule in rules:
        if rule.pattern is not None:
            by_name.setdefault(rule.pattern, []).append(rule.customer_id)
    candidates = {}
    for group in groups:
        name = group.get("name", "")
        if name in by_name:  # regra cadastrada vence o padrão `[Cliente]`
            names = [await session.get(Customer, i) for i in by_name[name]]
            found_all = [
                c for c in names if c and c.active and c.glpi_entity_id is not None
            ]
        else:
            found_all = []
            match = re.match(r"^\[\s*([^\]]+?)\s*\]", name)
            if match:
                try:
                    found_all.append(
                        await resolve_active_customer(session, match.group(1).strip())
                    )
                except AmbiguousCustomer:
                    raise
                except ValueError:
                    pass
        for found in found_all:
            candidates[found.id] = found
    if len(candidates) > 1:  # Generic monitoring group is not a customer.
        candidates = {i: c for i, c in candidates.items() if c.glpi_entity_id != 0}
    for rule in rules:  # `customer` é descartado quando `ignore_when_with` também casa
        if (
            rule.ignore_when_with_customer_id in candidates
            and rule.customer_id in candidates
        ):
            del candidates[rule.customer_id]
    if len(candidates) > 1:
        raise ValueError("Host associado a clientes distintos; ticket recusado")
    return next((c.display_name for c in candidates.values()), None)


async def canonical_customer(customer_name: str) -> tuple[str, int]:
    """(nome canônico, entidade GLPI) do cliente; é o nome gravado no incidente/ativo."""
    async with SessionLocal() as session:
        customer = await resolve_active_customer(session, customer_name)
    assert customer.glpi_entity_id is not None
    return customer.display_name, customer.glpi_entity_id


async def resolve_alert_customer(alert_data: Dict[str, Any]) -> tuple[str, str | None]:
    """(cliente, site `[ Cliente ] [ Site ]`) pelos grupos do host no Zabbix."""
    host_id = alert_data.get("host_id")
    site = None
    if host_id:
        hosts = await ZabbixClient()._call(
            "host.get",
            {"hostids": [host_id], "output": ["hostid"], "selectHostGroups": ["name"]},
        )
        if len(hosts) != 1:
            raise ValueError("Host Zabbix não encontrado ou não autorizado")
        groups = hosts[0].get("hostgroups", [])
        site = site_from_hostgroups([g.get("name", "") for g in groups])
        async with SessionLocal() as session:
            customer = await customer_from_hostgroups(session, groups)
        if customer:
            return customer, site
    return (
        resolve_customer_name(
            alert_data.get("host_name", ""), alert_data.get("tags", {})
        ),
        site,
    )


async def ensure_glpi_ticket(
    glpi: GLPIClient,
    *,
    fingerprint: str,
    entity_id: int,
    category_id: int,
    title: str,
    content: str,
    allow_create: bool,
    linked_item: dict | None = None,
    urgency: int = 3,
) -> tuple[int, bool]:
    """Return the single GLPI ticket for a fingerprint, creating it if absent."""
    marker = f"[n.infraops:{fingerprint}]"
    await glpi.change_active_entity(entity_id)
    existing_id = await glpi.find_ticket_by_name_marker(marker, entity_id)
    if existing_id is not None:
        return existing_id, False
    if not allow_create:
        raise GLPITransientError("GLPI ticket delivery awaits reconciliation")

    return await _create_glpi_ticket(
        glpi,
        marker=marker,
        entity_id=entity_id,
        category_id=category_id,
        title=title,
        content=content,
        linked_item=linked_item,
        urgency=urgency,
    )


async def _create_glpi_ticket(
    glpi: GLPIClient,
    *,
    marker: str,
    entity_id: int,
    category_id: int,
    title: str,
    content: str,
    linked_item: dict | None,
    urgency: int = 3,
) -> tuple[int, bool]:
    response = await glpi.create_ticket(
        title=f"{marker} {title}",
        content=content,
        entity_id=entity_id,
        itilcategories_id=category_id,
        urgency=urgency,
        **({"linked_item": linked_item} if linked_item else {}),
    )
    if isinstance(response, list) and response:
        ticket_id = response[0].get("id")
    elif isinstance(response, dict):
        ticket_id = response.get("id")
    else:
        ticket_id = None
    if not isinstance(ticket_id, int) or ticket_id <= 0:
        raise RuntimeError("GLPI não retornou um ID de ticket válido")

    await glpi.add_comment(
        ticket_id=ticket_id,
        content="Chamado gerado automaticamente pela plataforma n.infraops AIOps.",
        private=True,
    )
    return ticket_id, True


async def ensure_glpi_ticket_serialized(
    glpi: GLPIClient,
    *,
    fingerprint: str,
    entity_id: int,
    category_id: int,
    title: str,
    content: str,
    linked_item: dict | None = None,
    urgency: int = 3,
    lookup_first: bool = True,
) -> tuple[int, bool]:
    """Reserve one POST durably after lookup, before GLPI creation.

    lookup_first=False: o chamador já sabe (vínculo local) que não há chamado; a
    busca por marcador só roda se a reserva já foi consumida (POST incerto).
    """
    await glpi.change_active_entity(entity_id)
    marker = f"[n.infraops:{fingerprint}]"
    if lookup_first:
        existing_id = await glpi.find_ticket_by_name_marker(marker, entity_id)
        if existing_id is not None:
            return existing_id, False

    identity = f"glpi-ticket:{entity_id}:{fingerprint}".encode("utf-8")
    lock_key = int.from_bytes(
        blake2b(identity, digest_size=8).digest(), "big", signed=True
    )
    async with SessionLocal() as session:
        async with session.begin():
            try:
                await session.execute(text("SET LOCAL lock_timeout = '15s'"))
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_key)"),
                    {"lock_key": lock_key},
                )
            except OperationalError as exc:
                raise GLPITransientError(
                    "GLPI ticket lock temporarily unavailable"
                ) from exc
            claim = await session.execute(
                text(
                    "INSERT INTO n_infraops_glpi_ticket_post_reservations "
                    "(entity_id, fingerprint) VALUES (:entity_id, :fingerprint) "
                    "ON CONFLICT DO NOTHING RETURNING 1"
                ),
                {"entity_id": entity_id, "fingerprint": fingerprint},
            )
            allow_create = claim.scalar_one_or_none() == 1
    if allow_create:
        try:
            return await _create_glpi_ticket(
                glpi,
                marker=marker,
                entity_id=entity_id,
                category_id=category_id,
                title=title,
                content=content,
                linked_item=linked_item,
                urgency=urgency,
            )
        except GLPIPermanentError:
            # Refused (401/403): release the claim so a replay after the permission
            # fix can create it; the marker lookup above still prevents duplicates.
            async with SessionLocal() as session:
                async with session.begin():
                    await session.execute(
                        text(
                            "DELETE FROM n_infraops_glpi_ticket_post_reservations "
                            "WHERE entity_id = :entity_id AND fingerprint = :fingerprint"
                        ),
                        {"entity_id": entity_id, "fingerprint": fingerprint},
                    )
            raise
    return await ensure_glpi_ticket(
        glpi,
        fingerprint=fingerprint,
        entity_id=entity_id,
        category_id=category_id,
        title=title,
        content=content,
        linked_item=linked_item,
        allow_create=False,
    )


async def lookup_glpi_asset(host_id: str, customer: str) -> dict | None:
    async with SessionLocal() as session:
        asset = (
            await session.execute(
                select(Asset).where(
                    Asset.zabbix_host_id == host_id,
                    Asset.customer_id == customer.lower().strip(),
                )
            )
        ).scalar_one_or_none()
        if asset and asset.tags.get("glpi_item_id"):
            return {
                "itemtype": asset.tags["glpi_itemtype"],
                "id": asset.tags["glpi_item_id"],
            }
    return None


def build_glpi_ticket_content(alert_data: Dict[str, Any], analysis: Any) -> str:
    """Render untrusted alert and analysis text inside the GLPI HTML body."""
    host_name = escape(str(alert_data.get("host_name", "")))
    host_ip = escape(str(alert_data.get("host_ip", "Sem IP")))
    severity = escape(str(alert_data.get("severity", "AVERAGE")))
    cause = escape(str(analysis.probable_cause))
    urgency = escape(str(analysis.urgency))
    executive_plan = escape(str(analysis.executive_action_plan))
    technical_plan = escape(str(analysis.technical_action_plan))
    playbook = escape(str(analysis.recommended_playbook))
    return f"""
<h2>Relatório AIOps — Triagem de Incidente</h2>
<hr/>
<p><b>Host:</b> {host_name} ({host_ip})</p>
<p><b>Severidade do Alerta:</b> {severity}</p>
<p><b>Causa Provável:</b> {cause}</p>
<p><b>Opinião da IA (urgência):</b> {urgency}</p>
<p><b>Isolamento Requerido:</b> {"Sim" if analysis.isolation_required else "Não"}</p>
<hr/>
<h3>Plano de Ação Executivo:</h3>
<p>{executive_plan}</p>
<h3>Plano de Ação Técnico:</h3>
<p>{technical_plan}</p>
<h3>Playbook Recomendado:</h3>
<p><code>{playbook}</code></p>
"""


SEVERITY_NAMES = {
    0: "not_classified",
    1: "info",
    2: "warning",
    3: "average",
    4: "high",
    5: "disaster",
}


async def _ai_skip(customer_name: str) -> str | None:
    """Outcome da porta de IA; qualquer falha pula o modelo e o chamado segue."""
    try:
        async with SessionLocal() as session:
            return await ai_gate(session, customer_name.lower().strip())
    except Exception as exc:
        logger.warning("AI gate failed, skipping model: %s", type(exc).__name__)
        return "error"


async def _async_process_alert_v1(
    alert_data: Dict[str, Any], fingerprint: str
) -> Dict[str, Any]:
    """Grava o incidente para o painel; chamado só pelo decisor (ticket_decider).

    Repetição de um gatilho com chamado aberto vira comentário nesse chamado.
    """
    if str(alert_data.get("status", "PROBLEM")).upper() in {"RESOLVED", "OK"}:
        return await _async_process_recovery(alert_data, fingerprint)

    host_name = alert_data.get("host_name", "")
    customer, site = await resolve_alert_customer(alert_data)
    customer_name, entity_id = await canonical_customer(customer)
    key = dedup_key(
        entity_id,
        str(alert_data.get("host_id", "")),
        str(alert_data.get("trigger_id", "")),
    )
    severity = int(alert_data.get("severity", 3))
    event_id = str(alert_data.get("event_id", ""))
    logger.info(
        "Processando alerta v1 | Cliente: %s | Entity ID: %d", customer_name, entity_id
    )

    try:
        await LokiClient().send_json_log(
            tenant_id=customer_name,
            log_data={
                "alert": alert_data,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            },
            labels={
                "tenant_id": customer_name,
                "source": "aiops_engine",
                "severity": SEVERITY_NAMES.get(severity, "unknown"),
            },
        )
    except Exception as e:
        logger.error("Erro ao enviar logs estruturados para o Grafana Loki: %s", e)

    async with SessionLocal() as session:
        async with session.begin():
            db_incident = (
                await session.execute(
                    select(Incident).where(Incident.fingerprint == fingerprint)
                )
            ).scalar_one_or_none()
            incident_created = db_incident is None
            now = datetime.now(timezone.utc)
            db_asset = (
                await session.execute(
                    select(Asset).where(
                        Asset.zabbix_host_id == alert_data.get("host_id", ""),
                        Asset.customer_id == customer_name.lower().strip(),
                    )
                )
            ).scalar_one_or_none()
            asset_id = db_asset.id if db_asset else None

            if db_incident:
                db_incident.asset_id = asset_id
                if (db_incident.tags or {}).get("ninf_zabbix_event_id") != event_id:
                    db_incident.alert_count += 1
                db_incident.last_seen = now
                db_incident.updated_at = now
            else:
                db_incident = Incident(
                    fingerprint=fingerprint,
                    title=alert_data.get("trigger_name", "Unknown"),
                    severity=severity,
                    status="open",
                    host_id=alert_data.get("host_id", ""),
                    host_name=host_name,
                    trigger_id=alert_data.get("trigger_id", ""),
                    asset_id=asset_id,
                    alert_count=1,
                    first_seen=now,
                    last_seen=now,
                    sanitized_description=alert_data.get("trigger_description", ""),
                    tags=alert_data.get("tags", {}),
                )
                session.add(db_incident)

            old = db_incident.tags or {}
            db_incident.tags = {
                **old,
                "ninf_customer_name": customer_name,
                "ninf_entity_id": entity_id,
                "ninf_dedup_key": key,
                "ninf_zabbix_event_id": event_id,
                "ninf_zabbix_status": old.get("ninf_zabbix_status", "problem"),
                "ninf_ticket_state": old.get("ninf_ticket_state", "pending"),
                "ninf_branch": old.get("ninf_branch", "noc"),
                **({"ninf_site": site} if site else {}),
            }
            await session.flush()
            if incident_created:
                session.add(
                    IncidentAction(
                        incident_id=db_incident.id,
                        actor_source="zabbix",
                        action="incident_created",
                        new_status=db_incident.status,
                        new_assignee_id=db_incident.assigned_user_id,
                        note=f"event={event_id}",
                    )
                )
            link = await session.get(TicketLink, (entity_id, key))
            pending = db_incident.tags["ninf_ticket_state"] == "pending"
            attach_to = link.ticket_id if link and link.state == "open" else None
            incident_id = db_incident.id

    if attach_to and pending:
        glpi = GLPIClient()
        try:
            await glpi.init_session()
            await glpi.change_active_entity(entity_id)
            await glpi.add_comment(
                ticket_id=attach_to,
                content=(
                    f"Voltou a ocorrer às {datetime.now(timezone.utc):%H:%M} UTC "
                    f"(evento {escape(event_id)})."
                ),
                private=False,
            )
        finally:
            await glpi.kill_session()
        await attach_incident(incident_id, entity_id, key, attach_to)

    async with SessionLocal() as session:
        db_incident = await session.get(Incident, incident_id)
        assert db_incident is not None
        event_data = {
            "id": str(db_incident.id),
            "fingerprint": fingerprint,
            "title": db_incident.title,
            "severity": SEVERITY_NAMES.get(severity, "unknown"),
            "severity_level": severity,
            "host_name": host_name,
            "client": customer_name,
            "tenant_id": customer_name.lower().strip(),
            "status": db_incident.status,
            "source_status": db_incident.tags["ninf_zabbix_status"],
            "ticket_id": db_incident.deskmanager_ticket_id,
            "pipeline_stage": (
                "resolved"
                if db_incident.status == "resolved"
                else (
                    "ticket_opened"
                    if db_incident.deskmanager_ticket_id
                    else "incident_created"
                )
            ),
            "alert_count": db_incident.alert_count,
            "first_seen": db_incident.first_seen.isoformat(),
            "last_seen": db_incident.last_seen.isoformat(),
        }
    _publish_incident_event(event_data)
    return {
        "id": incident_id,
        "fingerprint": fingerprint,
        "ticket_id": attach_to,
    }


async def attach_incident(
    incident_id: int, entity_id: int, key: str, ticket_id: int
) -> None:
    """Liga o incidente ao chamado aberto da mesma chave e conta a ocorrência."""
    async with SessionLocal() as session:
        async with session.begin():
            incident = await session.get(Incident, incident_id, with_for_update=True)
            assert incident is not None
            if (incident.tags or {}).get("ninf_ticket_state") != "pending":
                return
            link = await session.get(TicketLink, (entity_id, key), with_for_update=True)
            assert link is not None
            link.occurrences += 1
            link.last_seen = datetime.now(timezone.utc)
            incident.deskmanager_ticket_id = str(ticket_id)
            incident.tags = {**incident.tags, "ninf_ticket_state": "attached"}
            session.add(
                IncidentAction(
                    incident_id=incident.id,
                    actor_source="glpi",
                    action="ticket_reused",
                    previous_status=incident.status,
                    new_status=incident.status,
                    previous_assignee_id=incident.assigned_user_id,
                    new_assignee_id=incident.assigned_user_id,
                    note=f"ticket={ticket_id} entity={entity_id}",
                )
            )


async def _async_process_recovery(
    alert_data: Dict[str, Any], fingerprint: str
) -> Dict[str, Any]:
    """Recuperação no Zabbix: resolve no Hub, libera sintomas e fecha o chamado intocado."""
    now = datetime.now(timezone.utc)
    event_data = None
    async with SessionLocal() as session:
        async with session.begin():
            incident = (
                await session.execute(
                    select(Incident)
                    .where(Incident.fingerprint == fingerprint)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if incident is None:
                raise LookupError("Problem incident has not been persisted yet")
            tags = incident.tags or {}
            if (
                str(tags.get("ninf_zabbix_event_id")) != str(alert_data.get("event_id"))
                or incident.host_id != str(alert_data.get("host_id"))
                or incident.trigger_id != str(alert_data.get("trigger_id"))
            ):
                raise ValueError("Recovery does not match original Zabbix event")
            entity_id = tags.get("ninf_entity_id")
            key = tags.get("ninf_dedup_key")
            result = {
                "id": incident.id,
                "fingerprint": fingerprint,
                "ticket_id": incident.deskmanager_ticket_id,
                "status": "source_recovered",
            }
            if tags.get("ninf_zabbix_status") != "resolved":
                previous_status = incident.status
                incident.tags = {
                    **tags,
                    "ninf_zabbix_status": "resolved",
                    "ninf_zabbix_recovered_at": now.isoformat(),
                }
                if incident.status not in ("resolved", "closed"):
                    incident.status = "resolved"
                incident.last_seen = now
                incident.updated_at = now
                session.add(
                    IncidentAction(
                        incident_id=incident.id,
                        actor_source="zabbix",
                        action="zabbix_recovered",
                        previous_status=previous_status,
                        new_status=incident.status,
                        previous_assignee_id=incident.assigned_user_id,
                        new_assignee_id=incident.assigned_user_id,
                        note=f"event={alert_data.get('event_id')}",
                    )
                )
                # Causa resolvida: sintomas ainda ativos voltam à fila com carência nova.
                symptoms = (
                    await session.execute(
                        select(Incident)
                        .where(
                            Incident.tags["ninf_cause_incident_id"].astext
                            == str(incident.id),
                            Incident.tags["ninf_ticket_state"].astext == "symptom",
                            Incident.tags["ninf_zabbix_status"].astext == "problem",
                        )
                        .with_for_update()
                    )
                ).scalars()
                for symptom in symptoms:
                    symptom.tags = {
                        **symptom.tags,
                        "ninf_ticket_state": "pending",
                        "ninf_grace_from": now.isoformat(),
                    }
                event_data = {
                    "id": str(incident.id),
                    "fingerprint": fingerprint,
                    "tenant_id": tags.get("ninf_customer_name", "").lower().strip(),
                    "status": incident.status,
                    "ticket_id": incident.deskmanager_ticket_id,
                    "source_status": "resolved",
                    "source_recovered_at": now.isoformat(),
                }
    if event_data:
        _publish_incident_event(event_data)
    if entity_id is not None and key:
        await close_ticket_if_recovered(int(entity_id), key, now)
    return result


async def close_ticket_if_recovered(entity_id: int, key: str, now: datetime) -> None:
    """Chave sem incidente ativo: soluciona o chamado se nenhum técnico mexeu.

    Com técnico, só comenta uma vez (source_resolved_at); o técnico fecha.
    Falha do GLPI propaga para o retry da task (o vínculo segue `open`).
    """
    async with SessionLocal() as session:
        link = await session.get(TicketLink, (entity_id, key))
        if link is None or link.state != "open" or link.source_resolved_at:
            return
        active = await session.scalar(
            select(Incident.id)
            .where(
                Incident.tags["ninf_dedup_key"].astext == key,
                Incident.tags["ninf_entity_id"].astext == str(entity_id),
                Incident.tags["ninf_zabbix_status"].astext == "problem",
            )
            .limit(1)
        )
        if active is not None:
            return
    ticket_id = link.ticket_id
    glpi = GLPIClient()
    try:
        await glpi.init_session()
        await glpi.change_active_entity(entity_id)
        if await glpi.has_technician(ticket_id):
            await glpi.add_comment(
                ticket_id=ticket_id,
                content=f"Resolvido na origem (Zabbix) às {now:%H:%M} UTC.",
                private=False,
            )
            values: dict[str, Any] = {"source_resolved_at": now}
        else:
            await glpi.solve_ticket(
                ticket_id, f"Resolvido na origem (Zabbix) às {now:%H:%M} UTC."
            )
            values = {"state": "auto_closed", "closed_at": now}
    finally:
        await glpi.kill_session()
    async with SessionLocal() as session:
        async with session.begin():
            row = await session.get(TicketLink, (entity_id, key), with_for_update=True)
            assert row is not None
            if row.ticket_id == ticket_id and row.state == "open":
                for name, value in values.items():
                    setattr(row, name, value)


async def _has_persisted_inhibition_completion(
    fingerprint: str, *, recovery: bool
) -> bool:
    """Check durable completion before treating a Redis inhibition as a duplicate."""
    async with SessionLocal() as session:
        statement = select(Incident.id).where(Incident.fingerprint == fingerprint)
        if recovery:
            statement = statement.where(
                Incident.tags["ninf_zabbix_status"].astext == "resolved"
            )
        return (await session.execute(statement)).scalar_one_or_none() is not None


async def _record_glpi_delivery_exhausted(fingerprint: str, *, retries: int) -> None:
    """Leave a durable, payload-free marker when automatic GLPI retry ends."""
    async with SessionLocal() as session:
        async with session.begin():
            incident_id = (
                await session.execute(
                    select(Incident.id).where(Incident.fingerprint == fingerprint)
                )
            ).scalar_one_or_none()
            if incident_id is not None:
                session.add(
                    IncidentAction(
                        incident_id=incident_id,
                        actor_source="glpi",
                        action="ticket_retry_exhausted",
                        note=f"retries={retries}",
                    )
                )


def _publish_incident_event(event_data: dict) -> None:
    redis_client = None
    try:
        redis_client = _get_sync_redis()
        redis_client.publish("ninf_incidents", json.dumps(event_data))
    except Exception as exc:
        logger.warning(
            "Persisted incident could not be published: %s", type(exc).__name__
        )
    finally:
        if redis_client is not None:
            try:
                redis_client.close()
            except Exception:
                logger.warning("Could not close incident publisher")


@celery_app.task(
    bind=True,
    name="app.workers.alerts.process_alert_v1",
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def process_alert_v1(
    self: Any,
    alert_data: dict[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    """Processa alerta v1 (AIOps pipeline).

    Implementa deduplicação/inibição com chaves SHA-256 no Redis (`ninf-redis`)
    com TTL de 300 segundos.
    """
    recovery = str(alert_data.get("status", "PROBLEM")).upper() in {"RESOLVED", "OK"}
    inhibit_key = f"ninf:inhibit:{fingerprint}{':recovery' if recovery else ''}"
    inhibit_token = uuid4().hex
    acquired = False

    try:
        redis = _get_sync_redis()
        try:
            acquired = bool(redis.set(inhibit_key, inhibit_token, ex=300, nx=True))
        finally:
            redis.close()
        if not acquired:
            if not asyncio.run(
                _has_persisted_inhibition_completion(fingerprint, recovery=recovery)
            ):
                logger.info(
                    "Inibição sem conclusão persistida; reagendando | fingerprint=%s",
                    fingerprint,
                )
                raise self.retry(countdown=settings.lock_retry_delay_seconds)
            logger.info(
                "Alerta DEDUPLICADO / INIBIDO | fingerprint=%s host=%s trigger=%s",
                fingerprint,
                alert_data.get("host_name"),
                alert_data.get("trigger_name"),
            )
            return {"status": "deduplicated", "fingerprint": fingerprint}

        logger.info(
            "Iniciando processamento AIOps | fingerprint=%s host=%s trigger=%s",
            fingerprint,
            alert_data.get("host_name"),
            alert_data.get("trigger_name"),
        )

        result = asyncio.run(_async_process_alert_v1(alert_data, fingerprint))
        return result

    except Retry:
        raise
    except Exception as exc:
        try:
            if acquired:
                redis_err = _get_sync_redis()
                try:
                    # A slow attempt must not delete a newer worker's inhibition.
                    redis_err.eval(
                        "if redis.call('get', KEYS[1]) == ARGV[1] then "
                        "return redis.call('del', KEYS[1]) else return 0 end",
                        1,
                        inhibit_key,
                        inhibit_token,
                    )
                finally:
                    redis_err.close()
        except Exception:
            pass
        if isinstance(exc, GLPIPermanentError):
            logger.error("GLPI permission denied; incident retained for manual repair")
            return {
                "status": "blocked",
                "fingerprint": fingerprint,
                "reason": "glpi_permission",
            }
        if isinstance(exc, GLPITransientError):
            if self.request.retries >= 12:
                try:
                    asyncio.run(
                        _record_glpi_delivery_exhausted(
                            fingerprint, retries=self.request.retries
                        )
                    )
                except Exception as audit_exc:
                    logger.error(
                        "Could not audit exhausted GLPI delivery: %s",
                        type(audit_exc).__name__,
                    )
                logger.error("GLPI delivery retries exhausted; incident retained")
                raise
            countdown = min(30 * 2 ** min(self.request.retries, 5), 900)
            logger.warning("GLPI temporarily unavailable; retry scheduled")
            raise self.retry(exc=exc, countdown=countdown, max_retries=12)
        logger.exception("Falha ao processar alerta v1 AIOps: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(name="app.workers.alerts.sweep_notifications")
def sweep_notifications() -> dict[str, int]:
    """Varredura P3: avisa casos novos e escala os sem reconhecimento na janela."""
    from app.services.notifications import sweep

    return asyncio.run(sweep())
