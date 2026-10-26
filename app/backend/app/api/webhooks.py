# -------------------------------------------------------
# NessOps — Endpoint Webhook Zabbix
# -------------------------------------------------------
"""
POST /webhook/zabbix — Ponto de entrada de alertas do Zabbix.

Usa o mesmo fingerprint por evento e worker de /v1/alerts.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, status
from redis.asyncio import Redis

from app.config import get_settings
from app.core.fingerprint import generate_event_fingerprint
from app.core.webhook_auth import verify_key
from app.dependencies import get_redis
from app.models.schemas import AlertResponse, GlpiWebhookPayload, ZabbixAlertPayload
from app.workers.alerts import process_alert_v1

logger = logging.getLogger(__name__)
settings = get_settings()


async def verify_webhook_key(x_api_key: str = Header(None, alias="X-Api-Key")):
    verify_key(settings.webhook_api_key, x_api_key)


router = APIRouter(
    prefix="/webhook", tags=["webhooks"], dependencies=[Depends(verify_webhook_key)]
)


@router.post(
    "/zabbix",
    response_model=AlertResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Recebe alertas do Zabbix via webhook",
    description="Endpoint para o Zabbix enviar alertas via webhook media type.",
)
async def receive_zabbix_alert(
    payload: ZabbixAlertPayload,
) -> AlertResponse:
    """Recebe alerta e o envia ao pipeline canônico de incidente e GLPI."""

    fingerprint = generate_event_fingerprint(payload)
    alert_data = payload.model_dump(mode="json")

    process_alert_v1.apply_async(
        args=[alert_data, fingerprint],
        queue="alerts.primary",
    )
    logger.info(
        "Alerta aceito | fingerprint=%s host=%s",
        fingerprint[:12],
        payload.host_name,
    )
    return AlertResponse(fingerprint=fingerprint, accepted=True, queue="primary")


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

    return {
        "status": "ignored",
        "reason": f"Status '{payload.status}' não requer tratativa",
    }


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check do webhook receiver",
)
async def health_check(redis: Redis = Depends(get_redis)) -> dict[str, str]:
    """Verifica conectividade com Redis."""
    await redis.ping()
    return {"status": "healthy", "service": "webhook-receiver"}
