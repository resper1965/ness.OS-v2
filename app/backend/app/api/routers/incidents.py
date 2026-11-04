# -------------------------------------------------------
# n.infraops — Router: Incidents
# Lista incidentes do PostgreSQL com pipeline_stage calculado
# -------------------------------------------------------
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Literal, Sequence
from urllib.parse import urlencode, urljoin

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field, field_validator
from redis.asyncio import Redis
from sqlalchemy import desc, func, select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.dependencies import (
    get_current_user,
    is_noc_role,
    require_noc,
    require_operator,
    resolve_tenant_scope,
)
from app.database import SessionLocal
from app.models import Incident, IncidentAction, SocDecision
from app.models.schemas import IncidentAnalyzeRequest
from app.models.users import User

logger = logging.getLogger(__name__)
router = APIRouter()
_stream_bearer = HTTPBearer(auto_error=False)

# Mapeamento severity → label
SEVERITY_LABEL = {
    0: "not_classified",
    1: "info",
    2: "warning",
    3: "average",
    4: "high",
    5: "disaster",
}


def _pipeline_stage(incident: Incident) -> str:
    """Calcula em qual etapa do pipeline o incidente está."""
    # Por enquanto derivado dos campos existentes.
    # Quando DeskManager e n8n forem integrados, estes campos serão persistidos.
    if incident.status in {"resolved", "closed"}:
        return "resolved"
    if incident.deskmanager_ticket_id:
        return "ticket_opened"
    if incident.alert_count and incident.alert_count > 0:
        # TODO: verificar se ticket_id existe (campo futuro)
        return "incident_created"
    return "detected"


_TICKET_ACTIONS = (
    "ticket_created",
    "ticket_reused",
    "ticket_failed",
    "ticket_retry_exhausted",
)
_TICKET_PENDING = {"ticket_failed", "ticket_retry_exhausted"}


def _ticket_state(inc: Incident, last_ticket_action: str | None) -> str:
    """ticketed | pending_sync | none, derivado sem coluna.

    ponytail: "tentativa em curso" não deixa rastro persistido (só o resultado
    da tentativa vira ação); upgrade path: gravar ação ticket_attempt no worker.
    """
    if inc.deskmanager_ticket_id:
        return "ticketed"
    return "pending_sync" if last_ticket_action in _TICKET_PENDING else "none"


async def _last_ticket_actions(
    session, incidents: Sequence[Incident]
) -> dict[int, str]:
    """Última ação de ticket por incidente (só dos que ainda não têm ticket)."""
    ids = [i.id for i in incidents if not i.deskmanager_ticket_id]
    if not ids:
        return {}
    rows = await session.execute(
        select(IncidentAction.incident_id, IncidentAction.action)
        .where(
            IncidentAction.incident_id.in_(ids),
            IncidentAction.action.in_(_TICKET_ACTIONS),
        )
        .distinct(IncidentAction.incident_id)
        .order_by(
            IncidentAction.incident_id,
            desc(IncidentAction.created_at),
            desc(IncidentAction.id),
        )
    )
    return {incident_id: action for incident_id, action in rows.all()}


def _incident_payload(inc: Incident, last_ticket_action: str | None = None) -> dict:
    tags = inc.tags or {}
    asset_tags = inc.asset.tags or {} if inc.asset else {}
    return {
        "id": str(inc.id),
        "fingerprint": inc.fingerprint,
        "ticket_id": inc.deskmanager_ticket_id,
        "solution": tags.get("glpi_solution"),
        "resolution_sync_status": tags.get("resolution_sync_status"),
        "asset_id": inc.asset_id,
        "asset": (
            {
                "name": inc.asset.hostname,
                "glpi_itemtype": asset_tags.get("glpi_itemtype"),
                "glpi_item_id": asset_tags.get("glpi_item_id"),
                "owner": asset_tags.get("owner"),
                "owner_group_id": asset_tags.get("glpi_owner_group_id"),
            }
            if inc.asset
            else None
        ),
        "title": inc.title,
        "severity": SEVERITY_LABEL.get(inc.severity or 0, "unknown"),
        "severity_level": inc.severity or 0,
        "host_name": inc.host_name or "unknown",
        "client": tags.get("ninf_customer_name")
        or (inc.asset.customer_name if inc.asset else "Não identificado"),
        "status": inc.status,
        "source_status": tags.get("ninf_zabbix_status", "unknown"),
        "source_recovered_at": tags.get("ninf_zabbix_recovered_at"),
        "assigned_user_id": getattr(inc, "assigned_user_id", None),
        "alert_count": inc.alert_count or 1,
        "first_seen": inc.first_seen.isoformat() if inc.first_seen else None,
        "last_seen": inc.last_seen.isoformat() if inc.last_seen else None,
        "age_seconds": (
            max(0, int((datetime.now(timezone.utc) - inc.first_seen).total_seconds()))
            if inc.first_seen
            else None
        ),
        "ticket_state": _ticket_state(inc, last_ticket_action),
        "pipeline_stage": _pipeline_stage(inc),
    }


class IncidentActionRequest(BaseModel):
    action: Literal["acknowledge", "assign_self", "comment", "resolve", "close"]
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note")
    @classmethod
    def nonblank_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("O comentário não pode estar vazio")
        return value


def _instant(name: str, value: str | None) -> datetime | None:
    """ISO 8601 com fuso explícito; sem fuso ou inválido → 422."""
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail=f"{name}: use ISO 8601 com fuso (ex.: 2026-11-04T10:00:00-03:00; "
            "codifique '+' como %2B)",
        )
    return parsed


@router.get(
    "/api/incidents",
    tags=["incidents"],
)
async def list_incidents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    assignee: int | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """Fila de incidentes ordenada por prioridade e depois por tempo de espera.

    Prioridade = severity desc; empate: abertos/reconhecidos (open, acknowledged)
    antes de resolved/closed. Depois, first_seen asc (quem espera há mais tempo
    primeiro) e id asc para estabilidade. ponytail: sem pesos além disso;
    upgrade path: SLA/criticidade do ativo quando houver dado confiável.
    `from`/`to` filtram first_seen (inclusivo, ISO 8601 com fuso).
    """
    scope = resolve_tenant_scope(current_user, tenant_id)
    since, until = _instant("from", from_), _instant("to", to)
    async with SessionLocal() as session:
        criteria = []
        if status:
            criteria.append(Incident.status == status)
        if assignee is not None:
            criteria.append(Incident.assigned_user_id == assignee)
        if since:
            criteria.append(Incident.first_seen >= since)
        if until:
            criteria.append(Incident.first_seen <= until)
        if scope:
            criteria.append(
                func.lower(Incident.tags["ninf_customer_name"].astext) == scope
            )
        total = (
            await session.execute(
                select(func.count()).select_from(Incident).where(*criteria)
            )
        ).scalar_one()
        stmt = (
            select(Incident)
            .options(selectinload(Incident.asset))
            .where(*criteria)
            .order_by(
                desc(Incident.severity),
                Incident.status.in_(("open", "acknowledged")).desc(),
                Incident.first_seen,
                Incident.id,
            )
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        incidents = result.scalars().all()
        last = await _last_ticket_actions(session, incidents)

        return {
            "incidents": [
                _incident_payload(inc, last.get(inc.id)) for inc in incidents
            ],
            "total": total,
        }


@router.post(
    "/api/incident/analyze",
    tags=["incidents"],
    status_code=202,
    dependencies=[Depends(require_noc)],
)
async def analyze_incident(
    request: IncidentAnalyzeRequest,
):
    """
    Recebe um incidente consolidado pelo pipeline interno,
    agenda a task no Celery para gerar RCA e Post-Mortem usando
    métricas e buscas reais, e retorna 202 Accepted.
    """
    from app.workers.postmortem import generate_postmortem_report

    logger.info(
        "Recebida solicitação de análise para incidente | fingerprint=%s ticket=%s",
        request.incident_data.get("fingerprint"),
        request.ticket_id,
    )

    generate_postmortem_report.apply_async(
        args=[request.incident_data, request.ticket_id],
        queue="ml",
    )

    return {
        "status": "accepted",
        "message": "Análise de causa raiz iniciada no Celery.",
    }


@router.get("/api/incidents/stream", tags=["incidents"])
async def stream_incidents(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Canal SSE (Server-Sent Events) para stream de novos incidentes em tempo real."""
    user_role = current_user.role
    user_tenant_id = current_user.tenant_id
    user_id = current_user.id

    async def session_is_current() -> bool:
        try:
            credentials = await _stream_bearer(request)
            async with SessionLocal() as session:
                user = await get_current_user(request, credentials, session)
            return (
                user.id == user_id
                and user.role == user_role
                and user.tenant_id == user_tenant_id
            )
        except HTTPException:
            return False
        except Exception:
            logger.warning("Falha ao revalidar sessão SSE", exc_info=True)
            return False

    async def event_generator():
        settings = get_settings()
        # Conecta no Redis de forma assíncrona
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe("ninf_incidents")
        logger.info(
            f"Conexão SSE aberta para o usuário role={user_role} (tenant={user_tenant_id})"
        )

        try:
            # Envia ping de conexão inicial estabelecida
            yield "event: ping\ndata: {}\n\n"

            while True:
                # Ler mensagem do Redis com timeout curto para enviar ping periódico
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=15.0
                )
                if not await session_is_current():
                    yield 'event: auth\ndata: {"status":"revoked"}\n\n'
                    break
                if message:
                    try:
                        data = json.loads(message["data"])
                        incident_tenant_id = data.get("tenant_id")

                        # Filtro Multi-tenant:
                        # Operadores noc/soc/admin recebem tudo.
                        # Clientes recebem apenas do próprio tenant_id.
                        if is_noc_role(user_role) or (
                            incident_tenant_id and incident_tenant_id == user_tenant_id
                        ):
                            yield f"event: incident\ndata: {json.dumps(data)}\n\n"
                    except Exception as err:
                        logger.error(f"Erro ao analisar payload no SSE: {err}")
                else:
                    # Keep-alive ping para manter a conexão aberta
                    yield "event: ping\ndata: {}\n\n"
        except asyncio.CancelledError:
            logger.info("Conexão SSE encerrada pelo cliente.")
        finally:
            await pubsub.unsubscribe("ninf_incidents")
            await pubsub.close()
            await client.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Evita buffering em Caddy/Nginx
        },
    )


@router.get("/api/incidents/{incident_id}", tags=["incidents"])
async def get_incident_detail(
    incident_id: int,
    current_user: User = Depends(get_current_user),
):
    """Return incident detail only within the authenticated user's tenant scope."""
    scope = resolve_tenant_scope(current_user, None)
    async with SessionLocal() as session:
        stmt = (
            select(Incident)
            .options(selectinload(Incident.asset))
            .where(Incident.id == incident_id)
        )
        if scope:
            stmt = stmt.where(
                func.lower(Incident.tags["ninf_customer_name"].astext) == scope
            )
        incident = (await session.execute(stmt)).scalar_one_or_none()
        if incident is None or (
            scope
            and (incident.tags or {}).get("ninf_customer_name", "").lower() != scope
        ):
            raise HTTPException(status_code=404, detail="Incidente não encontrado")
        event_id = (incident.tags or {}).get("ninf_zabbix_event_id")
        source_url = None
        if event_id and incident.trigger_id:
            source_url = (
                urljoin(get_settings().zabbix_url, "tr_events.php")
                + "?"
                + urlencode({"triggerid": incident.trigger_id, "eventid": event_id})
            )
        actions = (
            (
                await session.execute(
                    select(IncidentAction)
                    .where(IncidentAction.incident_id == incident.id)
                    .order_by(desc(IncidentAction.created_at), desc(IncidentAction.id))
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        last = await _last_ticket_actions(session, [incident])
        return {
            **_incident_payload(incident, last.get(incident.id)),
            "host_id": incident.host_id,
            "trigger_id": incident.trigger_id,
            "source_event_id": event_id,
            "source_url": source_url,
            "description": incident.sanitized_description,
            "actions": [
                {
                    "id": str(action.id),
                    "actor_user_id": action.actor_user_id,
                    "actor_source": action.actor_source,
                    "action": action.action,
                    "previous_status": action.previous_status,
                    "new_status": action.new_status,
                    "previous_assignee_id": action.previous_assignee_id,
                    "new_assignee_id": action.new_assignee_id,
                    "note": action.note,
                    "created_at": action.created_at.isoformat(),
                }
                for action in actions
            ],
        }


@router.get("/api/incidents/{incident_id}/timeline", tags=["incidents"])
async def get_incident_timeline(
    incident_id: int,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=10000),
    current_user: User = Depends(get_current_user),
):
    """Ações e decisões SOC vinculadas, em ordem cronológica ascendente, paginadas.

    A decisão só entra se `incident_id` bate E o tenant (customer_id) é o do incidente.
    ponytail: união feita em memória (offset+limit linhas por fonte); upgrade path:
    UNION ALL em SQL se a página ficar funda.
    """
    scope = resolve_tenant_scope(current_user, None)
    tenant_col = func.lower(Incident.tags["ninf_customer_name"].astext)
    async with SessionLocal() as session:
        stmt = select(tenant_col).where(Incident.id == incident_id)
        if scope:
            stmt = stmt.where(tenant_col == scope)
        found = (await session.execute(stmt)).first()
        if found is None:
            raise HTTPException(status_code=404, detail="Incidente não encontrado")
        tenant = found[0]
        a_where = IncidentAction.incident_id == incident_id
        d_where = (SocDecision.incident_id == incident_id) & (
            func.lower(SocDecision.customer_id) == tenant
        )
        total = (
            await session.execute(
                select(func.count()).select_from(IncidentAction).where(a_where)
            )
        ).scalar_one() + (
            await session.execute(
                select(func.count()).select_from(SocDecision).where(d_where)
            )
        ).scalar_one()
        n = offset + limit
        actions = (
            (
                await session.execute(
                    select(IncidentAction)
                    .where(a_where)
                    .order_by(IncidentAction.created_at, IncidentAction.id)
                    .limit(n)
                )
            )
            .scalars()
            .all()
        )
        decisions = (
            (
                await session.execute(
                    select(SocDecision)
                    .where(d_where)
                    .order_by(SocDecision.created_at, SocDecision.id)
                    .limit(n)
                )
            )
            .scalars()
            .all()
        )
        entries = [
            (
                a.created_at,
                "n_infraops_incident_actions",
                a.id,
                {
                    "kind": a.action,
                    "at": a.created_at.isoformat(),
                    "actor": {"source": a.actor_source, "user_id": a.actor_user_id},
                    "source_table": "n_infraops_incident_actions",
                    "source_id": str(a.id),
                    "note": a.note,
                },
            )
            for a in actions
        ] + [
            (
                d.created_at,
                "n_secops_soc_decisions",
                d.id,
                {
                    "kind": "soc_decision",
                    "at": d.created_at.isoformat(),
                    "actor": {"source": "soc_triage", "user_id": None},
                    "source_table": "n_secops_soc_decisions",
                    "source_id": str(d.id),
                    "note": f"{d.classification}: {d.action_taken}",
                },
            )
            for d in decisions
        ]
        entries.sort(key=lambda e: e[:3])
        return {
            "entries": [e[3] for e in entries[offset:n]],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.post("/api/incidents/{incident_id}/actions", tags=["incidents"])
async def act_on_incident(
    incident_id: int,
    body: IncidentActionRequest,
    current_user: User = Depends(require_operator),
):
    """Apply an operator action and append its audit row in one transaction."""
    if body.action in {"comment", "resolve"} and not body.note:
        raise HTTPException(status_code=422, detail="Comentário obrigatório")
    scope = resolve_tenant_scope(current_user, None)
    async with SessionLocal() as session:
        async with session.begin():
            stmt = select(Incident).where(Incident.id == incident_id)
            if scope:
                stmt = stmt.where(
                    func.lower(Incident.tags["ninf_customer_name"].astext) == scope
                )
            incident = (
                await session.execute(stmt.with_for_update())
            ).scalar_one_or_none()
            if incident is None or (
                scope
                and (incident.tags or {}).get("ninf_customer_name", "").lower() != scope
            ):
                raise HTTPException(status_code=404, detail="Incidente não encontrado")

            previous_status = incident.status
            previous_assignee = incident.assigned_user_id
            if body.action == "acknowledge":
                if incident.status != "open":
                    raise HTTPException(status_code=409, detail="Estado incompatível")
                incident.status = "acknowledged"
            elif body.action == "assign_self":
                if incident.status == "closed":
                    raise HTTPException(status_code=409, detail="Incidente encerrado")
                if incident.assigned_user_id == current_user.id:
                    return {
                        "id": str(incident.id),
                        "status": incident.status,
                        "assigned_user_id": incident.assigned_user_id,
                    }
                incident.assigned_user_id = current_user.id
            elif body.action == "resolve":
                if incident.status not in {"open", "acknowledged"} or (
                    incident.deskmanager_ticket_id
                    and not (incident.tags or {}).get("glpi_resolved_at")
                ):
                    raise HTTPException(
                        status_code=409, detail="Resolução GLPI pendente"
                    )
                incident.status = "resolved"
            elif body.action == "close":
                if incident.status != "resolved" or (
                    incident.deskmanager_ticket_id
                    and (incident.tags or {}).get("resolution_sync_status") != "synced"
                ):
                    raise HTTPException(
                        status_code=409, detail="Resolução não sincronizada"
                    )
                incident.status = "closed"

            session.add(
                IncidentAction(
                    incident_id=incident.id,
                    actor_user_id=current_user.id,
                    actor_source="user",
                    action=body.action,
                    previous_status=previous_status,
                    new_status=incident.status,
                    previous_assignee_id=previous_assignee,
                    new_assignee_id=incident.assigned_user_id,
                    note=body.note,
                )
            )
        return {
            "id": str(incident.id),
            "status": incident.status,
            "assigned_user_id": incident.assigned_user_id,
        }
