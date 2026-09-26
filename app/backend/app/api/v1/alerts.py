import logging

from fastapi import APIRouter, Depends, Header, status
from redis.asyncio import Redis

from app.config import get_settings
from app.core.fingerprint import generate_event_fingerprint
from app.core.webhook_auth import verify_key
from app.dependencies import get_redis
from app.models.schemas import AlertResponse, ZabbixAlertPayload
from app.workers.alerts import process_alert_v1

logger = logging.getLogger(__name__)
settings = get_settings()


async def verify_api_key(x_api_key: str = Header(None, alias="X-Api-Key")):
    verify_key(settings.webhook_api_key, x_api_key)


router = APIRouter(
    prefix="/v1", tags=["alerts"], dependencies=[Depends(verify_api_key)]
)


@router.post(
    "/alerts",
    response_model=AlertResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Recebe alertas externos e processa via AIOps",
)
async def receive_alert(
    payload: ZabbixAlertPayload,
    redis: Redis = Depends(get_redis),
) -> AlertResponse:
    """Endpoint de ingestão de alertas v1.

    Valida a API Key, gera o fingerprint, e enfileira no Celery para deduplicação e processamento.
    """
    fingerprint = generate_event_fingerprint(payload)
    alert_data = payload.model_dump(mode="json")

    process_alert_v1.apply_async(
        args=[alert_data, fingerprint],
        queue="alerts.primary",
    )

    logger.info(
        "Alerta v1 recebido e enfileirado | fingerprint=%s host=%s",
        fingerprint[:12],
        payload.host_name,
    )

    return AlertResponse(
        fingerprint=fingerprint,
        accepted=True,
        queue="primary",
    )
