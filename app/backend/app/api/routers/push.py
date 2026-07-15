# -------------------------------------------------------
# n.infraops — Router: Web Push Subscriptions
# -------------------------------------------------------
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.core.dependencies import get_current_user
from app.models.users import User
from app.models.push import PushSubscription
from app.models.schemas import PushSubscribeRequest, PushUnsubscribeRequest

logger = logging.getLogger("nessops.api.push")
router = APIRouter(prefix="/api/v1/push", tags=["push-notifications"])


@router.get("/config")
async def get_push_config():
    """Retorna a chave pública VAPID necessária para o registro no navegador."""
    settings = get_settings()
    if not settings.vapid_public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de notificações push não configurado (chave pública VAPID ausente).",
        )
    return {"public_key": settings.vapid_public_key}


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe_push(
    request: PushSubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Registra uma inscrição de notificação push vinculada ao tenant do usuário logado."""
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário logado não possui um tenant_id associado.",
        )

    # Verificar se já existe subscrição para este endpoint
    stmt = select(PushSubscription).where(PushSubscription.endpoint == request.endpoint)
    res = await db.execute(stmt)
    existing_sub = res.scalar_one_or_none()

    if existing_sub:
        # Atualiza a subscrição existente
        existing_sub.tenant_id = current_user.tenant_id
        existing_sub.user_id = current_user.id
        existing_sub.auth_key = request.keys.auth
        existing_sub.p256dh_key = request.keys.p256dh
        logger.info(f"Subscrição de push atualizada para o usuário {current_user.email} (tenant={current_user.tenant_id})")
    else:
        # Cria uma nova subscrição
        new_sub = PushSubscription(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            endpoint=request.endpoint,
            auth_key=request.keys.auth,
            p256dh_key=request.keys.p256dh,
        )
        db.add(new_sub)
        logger.info(f"Nova subscrição de push criada para o usuário {current_user.email} (tenant={current_user.tenant_id})")

    await db.commit()
    return {"status": "success", "message": "Inscrição de notificações push registrada."}


@router.post("/unsubscribe")
async def unsubscribe_push(
    request: PushUnsubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove uma inscrição de notificação push do banco de dados."""
    stmt = delete(PushSubscription).where(PushSubscription.endpoint == request.endpoint)
    res = await db.execute(stmt)
    await db.commit()

    if res.rowcount == 0:
        logger.warning(f"Tentativa de desinscrição para endpoint inexistente de {current_user.email}")
        return {"status": "not_found", "message": "Inscrição não encontrada."}

    logger.info(f"Subscrição de push removida para o usuário {current_user.email}")
    return {"status": "success", "message": "Inscrição de notificações push removida."}
