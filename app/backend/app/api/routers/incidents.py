# -------------------------------------------------------
# n.infraops — Router: Incidents
# Lista incidentes do PostgreSQL com pipeline_stage calculado
# -------------------------------------------------------
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy import desc, select

from app.config import get_settings
from app.core.dependencies import (
    get_current_user,
    is_noc_role,
    is_session_version_current,
    require_noc,
    resolve_tenant_scope,
)
from app.core.jwt import verify_token
from app.core.session import SESSION_COOKIE_NAME
from app.database import SessionLocal
from app.models import Incident
from app.models.schemas import IncidentAnalyzeRequest
from app.models.users import User

logger = logging.getLogger(__name__)
router = APIRouter()

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
    if incident.status == "resolved":
        return "resolved"
    if incident.deskmanager_ticket_id:
        return "ticket_opened"
    if incident.alert_count and incident.alert_count > 0:
        # TODO: verificar se ticket_id existe (campo futuro)
        return "incident_created"
    return "detected"


async def _load_stream_user(request: Request) -> User | None:
    """Reload the authenticated user from the current credential and database."""
    authorization = request.headers.get("authorization", "")
    token = (
        authorization[7:].strip()
        if authorization.lower().startswith("bearer ")
        else request.cookies.get(SESSION_COOKIE_NAME)
    )
    if not token:
        return None
    try:
        payload = verify_token(token)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError):
        return None

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if (
            not user
            or not user.is_active
            or not is_session_version_current(payload, user)
        ):
            return None
        return user


@router.get(
    "/api/incidents",
    tags=["incidents"],
)
async def list_incidents(
    limit: int = Query(default=20, le=100),
    status: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """Retorna lista de incidentes com stage do pipeline."""
    from sqlalchemy.orm import selectinload

    scope = resolve_tenant_scope(current_user, tenant_id)
    async with SessionLocal() as session:
        stmt = (
            select(Incident)
            .options(selectinload(Incident.asset))
            .order_by(desc(Incident.last_seen))
            .limit(limit)
        )
        if status:
            stmt = stmt.where(Incident.status == status)
        if scope:
            from sqlalchemy import func

            stmt = stmt.where(
                func.lower(Incident.tags["ninf_customer_name"].astext) == scope
            )
        result = await session.execute(stmt)
        incidents = result.scalars().all()

        return {
            "incidents": [
                {
                    "id": str(inc.id),
                    "fingerprint": inc.fingerprint,
                    "ticket_id": inc.deskmanager_ticket_id,
                    "solution": (inc.tags or {}).get("glpi_solution"),
                    "resolution_sync_status": (inc.tags or {}).get(
                        "resolution_sync_status"
                    ),
                    "asset_id": inc.asset_id,
                    "asset": (
                        {
                            "name": inc.asset.hostname,
                            "glpi_itemtype": inc.asset.tags.get("glpi_itemtype"),
                            "glpi_item_id": inc.asset.tags.get("glpi_item_id"),
                            "owner": inc.asset.tags.get("owner"),
                            "owner_group_id": inc.asset.tags.get("glpi_owner_group_id"),
                        }
                        if inc.asset
                        else None
                    ),
                    "title": inc.title,
                    "severity": SEVERITY_LABEL.get(inc.severity or 0, "unknown"),
                    "severity_level": inc.severity or 0,
                    "host_name": inc.host_name or "unknown",
                    "client": (inc.tags or {}).get("ninf_customer_name")
                    or (inc.asset.customer_name if inc.asset else "Não identificado"),
                    "status": inc.status,
                    "alert_count": inc.alert_count or 1,
                    "first_seen": (
                        inc.first_seen.isoformat() if inc.first_seen else None
                    ),
                    "last_seen": inc.last_seen.isoformat() if inc.last_seen else None,
                    "pipeline_stage": _pipeline_stage(inc),
                }
                for inc in incidents
            ],
            "total": len(incidents),
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
    initial_identity = (current_user.id, current_user.role, current_user.tenant_id)

    async def event_generator():
        settings = get_settings()
        # Conecta no Redis de forma assíncrona
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe("ninf_incidents")
        logger.info(
            "Conexão SSE aberta para o usuário id=%s role=%s tenant=%s",
            *initial_identity,
        )

        try:
            next_revalidation = 0.0
            # Envia ping de conexão inicial estabelecida
            yield "event: ping\ndata: {}\n\n"

            while True:
                # Ler mensagem do Redis com timeout curto para enviar ping periódico
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=15.0
                )
                now = asyncio.get_running_loop().time()
                if now >= next_revalidation:
                    try:
                        active_user = await _load_stream_user(request)
                    except Exception:
                        logger.exception("Falha ao revalidar sessão SSE; encerrando stream")
                        active_user = None
                    active_identity = (
                        (active_user.id, active_user.role, active_user.tenant_id)
                        if active_user
                        else None
                    )
                    if active_identity != initial_identity:
                        yield 'event: auth\ndata: {"reason":"session_invalid"}\n\n'
                        return
                    next_revalidation = now + 15.0

                if message:
                    try:
                        data = json.loads(message["data"])
                        incident_tenant_id = data.get("tenant_id")

                        # Filtro Multi-tenant:
                        # Operadores noc/soc/admin recebem tudo.
                        # Clientes recebem apenas do próprio tenant_id.
                        if is_noc_role(active_user.role) or (
                            incident_tenant_id
                            and incident_tenant_id == active_user.tenant_id
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
