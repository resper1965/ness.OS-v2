# -------------------------------------------------------
# n.infraops — Integração Web Push (Google, Apple, Mozilla)
# -------------------------------------------------------
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from pywebpush import WebPushException, webpush
from sqlalchemy import delete

from app.config import get_settings
from app.database import SessionLocal
from app.models.push import PushSubscription

logger = logging.getLogger("nessops.integrations.webpush")


def _dispatch_web_push_sync(
    endpoint: str,
    auth_key: str,
    p256dh_key: str,
    payload: dict[str, Any],
    private_key: str,
    claims_email: str,
) -> bool:
    """Executa o post HTTP criptografado de forma síncrona para o endpoint do navegador."""
    try:
        response = webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {
                    "auth": auth_key,
                    "p256dh": p256dh_key,
                },
            },
            data=json.dumps(payload),
            vapid_private_key=private_key,
            vapid_claims={"sub": f"mailto:{claims_email}"},
            timeout=10,
        )
        logger.debug(
            f"Web Push enviado. Status={response.status_code}, Body={response.text}"
        )
        return response.ok
    except WebPushException as ex:
        # Se retornar 410 Gone ou 404 Not Found, o token expirou ou é inválido
        if ex.response is not None and ex.response.status_code in (404, 410):
            logger.warning(
                f"Inscrição Web Push expirada/inválida (status {ex.response.status_code}) para o endpoint {endpoint[:30]}..."
            )
            # Retorna falso para sinalizar remoção do banco
            return False
        logger.error(f"Erro de criptografia/envio do Web Push: {ex}")
        raise
    except Exception as ex:
        logger.error(f"Erro inesperado no envio de Web Push: {ex}")
        raise


async def send_web_push(
    subscription: PushSubscription, payload: dict[str, Any]
) -> bool:
    """
    Envia uma notificação push de forma assíncrona usando threads.
    Se a inscrição estiver expirada (Gone/410), ela é automaticamente removida do banco.
    """
    settings = get_settings()
    if not settings.vapid_private_key or not settings.vapid_public_key:
        logger.error("Chaves VAPID ausentes nas configurações. Envio abortado.")
        return False

    # Executa a chamada bloqueante em uma thread separada do event loop
    try:
        ok = await asyncio.to_thread(
            _dispatch_web_push_sync,
            endpoint=subscription.endpoint,
            auth_key=subscription.auth_key,
            p256dh_key=subscription.p256dh_key,
            payload=payload,
            private_key=settings.vapid_private_key,
            claims_email=settings.vapid_claims_email,
        )

        # Se a inscrição expirou (retornou False), remove do banco
        if ok is False:
            async with SessionLocal() as session:
                stmt = delete(PushSubscription).where(
                    PushSubscription.id == subscription.id
                )
                await session.execute(stmt)
                await session.commit()
                logger.info(
                    f"Subscrição ID {subscription.id} removida por expiração (410/404)."
                )
            return False

        return True
    except Exception as e:
        logger.error(
            f"Falha ao processar o envio de Web Push para a subscrição ID {subscription.id}: {e}"
        )
        return False


async def notify_tenant_stakeholders(
    tenant_id: str,
    title: str,
    body: str,
    incident_id: str | None = None,
    fingerprint: str | None = None,
    severity: str | None = None,
) -> int:
    """
    Recupera todas as subscrições ativas do tenant e despacha as notificações push em paralelo.
    Retorna o número de envios iniciados com sucesso.
    """
    from sqlalchemy import select

    async with SessionLocal() as session:
        stmt = select(PushSubscription).where(PushSubscription.tenant_id == tenant_id)
        res = await session.execute(stmt)
        subscriptions = res.scalars().all()

    if not subscriptions:
        logger.debug(
            f"Nenhum stakeholder cadastrado para receber pushes no tenant: {tenant_id}"
        )
        return 0

    # Estrutura do payload de push para o Service Worker
    payload = {
        "title": title,
        "body": body,
        "incident_id": incident_id,
        "fingerprint": fingerprint,
        "severity": severity,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }

    # Remove itens vazios
    payload = {k: v for k, v in payload.items() if v is not None}

    logger.info(
        f"Despachando Web Push para {len(subscriptions)} stakeholders do tenant: {tenant_id}"
    )

    # Dispara os envios concorrentemente
    tasks = [send_web_push(sub, payload) for sub in subscriptions]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = sum(1 for r in results if r is True)
    logger.info(
        f"Concluído envio de Web Push para o tenant {tenant_id}: {success_count} com sucesso, {len(subscriptions) - success_count} falhas/removidos."
    )

    return success_count
