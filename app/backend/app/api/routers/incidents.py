# -------------------------------------------------------
# n.infraops — Router: Incidents
# Lista incidentes do PostgreSQL com pipeline_stage calculado
# -------------------------------------------------------
from __future__ import annotations
import logging
import json
import asyncio
from fastapi import APIRouter, Query, status, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from app.database import SessionLocal
from app.models import Incident
from app.models.schemas import IncidentAnalyzeRequest
from app.core.jwt import verify_token
from app.config import get_settings
from redis.asyncio import Redis

logger = logging.getLogger(__name__)
router = APIRouter()

# Mapeamento severity → label
SEVERITY_LABEL = {
    0: "not_classified", 1: "info", 2: "warning",
    3: "average", 4: "high", 5: "disaster",
}


def _pipeline_stage(incident: Incident) -> str:
    """Calcula em qual etapa do pipeline o incidente está."""
    # Por enquanto derivado dos campos existentes.
    # Quando DeskManager e n8n forem integrados, estes campos serão persistidos.
    if incident.status == "resolved":
        return "postmortem"
    if incident.alert_count and incident.alert_count > 0:
        # TODO: verificar se ticket_id existe (campo futuro)
        return "incident_created"
    return "detected"


@router.get("/api/incidents", tags=["incidents"])
async def list_incidents(
    limit: int = Query(default=20, le=100),
    status: str | None = Query(default=None),
):
    """Retorna lista de incidentes com stage do pipeline."""
    from sqlalchemy.orm import selectinload
    async with SessionLocal() as session:
        stmt = select(Incident).options(selectinload(Incident.asset)).order_by(desc(Incident.last_seen)).limit(limit)
        if status:
            stmt = stmt.where(Incident.status == status)
        result = await session.execute(stmt)
        incidents = result.scalars().all()

        return {
            "incidents": [
                {
                    "id": str(inc.id),
                    "title": inc.title,
                    "severity": SEVERITY_LABEL.get(inc.severity or 0, "unknown"),
                    "severity_level": inc.severity or 0,
                    "host_name": inc.host_name or "unknown",
                    "client": inc.asset.customer_name if inc.asset else "Ness",
                    "status": inc.status,
                    "alert_count": inc.alert_count or 1,
                    "first_seen": inc.first_seen.isoformat() if inc.first_seen else None,
                    "last_seen": inc.last_seen.isoformat() if inc.last_seen else None,
                    "pipeline_stage": _pipeline_stage(inc),
                }
                for inc in incidents
            ],
            "total": len(incidents),
        }


@router.post("/api/incident/analyze", tags=["incidents"], status_code=202)
async def analyze_incident(
    request: IncidentAnalyzeRequest,
):
    """
    Recebe um alerta correlacionado (ex: via Keep AIOps),
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

    return {"status": "accepted", "message": "Análise de causa raiz iniciada no Celery."}


@router.get("/api/incidents/stream", tags=["incidents"])
async def stream_incidents(
    token: str = Query(..., description="JWT Token de acesso para autenticação")
):
    """Canal SSE (Server-Sent Events) para stream de novos incidentes em tempo real."""
    try:
        payload = verify_token(token)
        user_role = payload.get("role")
        user_tenant_id = payload.get("tenant_id")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso inválido ou expirado.",
        )

    async def event_generator():
        settings = get_settings()
        # Conecta no Redis de forma assíncrona
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe("ninf_incidents")
        logger.info(f"Conexão SSE aberta para o usuário role={user_role} (tenant={user_tenant_id})")

        try:
            # Envia ping de conexão inicial estabelecida
            yield "event: ping\ndata: {}\n\n"
            
            while True:
                # Ler mensagem do Redis com timeout curto para enviar ping periódico
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
                if message:
                    try:
                        data = json.loads(message["data"])
                        incident_tenant_id = data.get("tenant_id")
                        
                        # Filtro Multi-tenant:
                        # Operadores noc/soc/admin recebem tudo.
                        # Clientes recebem apenas do próprio tenant_id.
                        if user_role in ("noc", "soc", "admin") or (incident_tenant_id and incident_tenant_id == user_tenant_id):
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
        }
    )

