# -------------------------------------------------------
# NessOps — Endpoint Webhook Zabbix
# -------------------------------------------------------
"""
POST /webhook/zabbix — Ponto de entrada de alertas do Zabbix.

Fluxo de concorrência:
  1. Gera fingerprint SHA-256 do par (host_id, trigger_id).
  2. Tenta adquirir lock distribuído no Redis (SET NX EX).
  3. Lock OK → envia para fila "alerts.primary".
  4. Lock falha → envia para fila "alerts.deferred" com delay.
  5. Retorna 202 Accepted imediatamente (fire-and-forget).
"""
from __future__ import annotations

import logging
import httpx

from fastapi import APIRouter, Depends, status, Header, HTTPException, BackgroundTasks
from redis.asyncio import Redis

from app.config import get_settings
from app.core.fingerprint import generate_fingerprint
from app.core.locks import try_acquire_lock
from app.dependencies import get_redis
from app.models.schemas import AlertResponse, ZabbixAlertPayload, GlpiWebhookPayload
from app.workers.tasks import process_alert, process_deferred_alert

logger = logging.getLogger(__name__)
settings = get_settings()

async def verify_webhook_key(x_api_key: str = Header(None, alias="X-Api-Key")):
    if not settings.webhook_api_key:
        logger.warning("Webhook authentication is disabled (NINF_WEBHOOK_API_KEY is empty).")
        return
    if x_api_key != settings.webhook_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")

router = APIRouter(prefix="/webhook", tags=["webhooks"], dependencies=[Depends(verify_webhook_key)])


async def forward_to_keep(payload: ZabbixAlertPayload):
    """Retransmite o alerta de forma transparente para o Keep (AIOps Hub)."""
    if not settings.keep_url:
        return

    # Mapeamento do payload para garantir compatibilidade com zabbix-correlation.yml
    keep_payload = {
        "name": payload.trigger_name,
        "source": ["zabbix"],
        "status": "firing" if payload.status.upper() == "PROBLEM" else "resolved",
        "severity": payload.severity.name.lower(),
        "host": {
            "name": payload.host_name,
            "ip": payload.host_ip,
            "id": payload.host_id
        },
        "trigger": {
            "id": payload.trigger_id,
            "name": payload.trigger_name,
            "description": payload.trigger_description
        },
        "trigger_id": payload.trigger_id,
        "event_id": payload.event_id,
        "timestamp": payload.timestamp.isoformat(),
        "tags": payload.tags
    }

    url = f"{settings.keep_url.rstrip('/')}/alerts/event"
    headers = {"Content-Type": "application/json"}
    if settings.keep_api_key:
        headers["X-API-KEY"] = settings.keep_api_key

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=keep_payload, headers=headers, timeout=5.0)
            resp.raise_for_status()
            logger.info("Alerta Zabbix retransmitido com sucesso para o Keep.")
    except Exception as exc:
        logger.error(f"Erro ao retransmitir alerta para o Keep: {exc}")


@router.post(
    "/zabbix",
    response_model=AlertResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Recebe alertas do Zabbix via webhook",
    description="Endpoint para o Zabbix enviar alertas via webhook media type.",
)
async def receive_zabbix_alert(
    payload: ZabbixAlertPayload,
    background_tasks: BackgroundTasks,
    redis: Redis = Depends(get_redis),
) -> AlertResponse:
    """Recebe alerta, gera fingerprint, roteia via lock distribuído e repassa ao Keep."""

    # Retransmite o alerta para o Keep em background
    background_tasks.add_task(forward_to_keep, payload)

    fingerprint = generate_fingerprint(payload)
    alert_data = payload.model_dump(mode="json")

    # Tenta adquirir lock distribuído
    acquired = await try_acquire_lock(
        redis=redis,
        fingerprint=fingerprint,
        ttl_seconds=settings.lock_ttl_seconds,
    )

    if acquired:
        # Lock adquirido → processamento primário (cria incidente)
        process_alert.apply_async(
            args=[alert_data, fingerprint],
            queue="alerts.primary",
        )
        logger.info(
            "Alerta aceito [PRIMARY] | fingerprint=%s host=%s",
            fingerprint[:12],
            payload.host_name,
        )
        return AlertResponse(
            fingerprint=fingerprint,
            accepted=True,
            queue="primary",
        )
    else:
        # Lock já existe → outro worker está criando o incidente
        # Rota para fila secundária com delay
        process_deferred_alert.apply_async(
            args=[alert_data, fingerprint],
            queue="alerts.deferred",
            countdown=settings.lock_retry_delay_seconds,
        )
        logger.info(
            "Alerta aceito [DEFERRED] | fingerprint=%s host=%s",
            fingerprint[:12],
            payload.host_name,
        )
        return AlertResponse(
            fingerprint=fingerprint,
            accepted=True,
            queue="deferred",
        )


@router.post(
    "/glpi",
    status_code=status.HTTP_200_OK,
    summary="Recebe notificações de resolução do GLPI",
)
async def receive_glpi_resolution(
    payload: GlpiWebhookPayload,
) -> dict[str, Any]:
    """Recebe notificação de resolução de ticket no GLPI e despacha a tratativa."""
    logger.info(
        "Recebido webhook do GLPI | ticket_id=%s status=%s",
        payload.ticket_id,
        payload.status,
    )
    
    # Se o status for de solução/resolução (status 5 ou 6, ou nomes solved/resolved/closed)
    if payload.status.lower() in ("solved", "resolved", "closed", "5", "6"):
        from app.workers.tasks import process_ticket_resolution
        
        process_ticket_resolution.delay(
            ticket_id=payload.ticket_id,
            solution_text=payload.solution,
        )
        return {"status": "dispatched", "ticket_id": payload.ticket_id}
        
    return {"status": "ignored", "reason": f"Status '{payload.status}' não requer tratativa"}


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check do webhook receiver",
)
async def health_check(redis: Redis = Depends(get_redis)) -> dict[str, str]:
    """Verifica conectividade com Redis."""
    await redis.ping()
    return {"status": "healthy", "service": "webhook-receiver"}
