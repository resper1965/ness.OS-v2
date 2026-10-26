# -------------------------------------------------------
# n.infraops — Celery Tasks (processamento de alertas)
# -------------------------------------------------------
"""
Tasks assíncronas que processam alertas do Zabbix.

Fluxo:
  1. Webhook recebe alerta → gera fingerprint → tenta lock
  2. Lock OK → process_alert (fila primary)
  3. Lock falha → process_deferred_alert (fila deferred, com delay)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncio
from redis import Redis
from sqlalchemy import select

from app.config import get_settings
from app.core.sanitizer import sanitize, sanitize_dict
from app.database import SessionLocal
from app.integrations.n8n import notify_incident_created
from app.models import Incident, Asset
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_sync_redis() -> Redis:
    """Redis síncrono para uso dentro do Celery worker."""
    return Redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_alert",
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def process_alert(
    self: Any,
    alert_data: dict[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    """Processa alerta primário (lock adquirido).

    1. Sanitiza dados sensíveis.
    2. Cria ou atualiza incidente no PostgreSQL.
    3. Libera o lock no Redis.
    """
    try:
        logger.info(
            "Processando alerta | fingerprint=%s host=%s trigger=%s",
            fingerprint,
            alert_data.get("host_name"),
            alert_data.get("trigger_name"),
        )

        # --- 1. Sanitização (CISO-Mindset) ---
        sanitized = _sanitize_alert(alert_data)

        # --- 2. Upsert incidente no PostgreSQL ---
        incident = asyncio.run(_async_upsert_incident(fingerprint, sanitized))

        # --- 3. Liberar lock ---
        redis = _get_sync_redis()
        lock_key = f"ninf:lock:{fingerprint}"
        redis.delete(lock_key)
        redis.close()

        # --- 4. Notificar n8n (DeskManager + WhatsApp) ---
        n8n_result = notify_incident_created(incident)
        ticket_id = n8n_result.get("ticket_id")

        # --- 5. Agendar geração de post-mortem ---
        if incident.get("action") == "created":
            from app.workers.postmortem import generate_postmortem_report

            generate_postmortem_report.apply_async(
                args=[incident, ticket_id],
                queue="ml",
                countdown=30,  # Aguarda 30s para consolidar alertas
            )

        logger.info(
            "Incidente processado | fingerprint=%s alerts=%d ticket=%s",
            fingerprint,
            incident["alert_count"],
            ticket_id,
        )
        return incident

    except Exception as exc:
        logger.exception("Falha ao processar alerta: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_deferred_alert",
    max_retries=5,
    default_retry_delay=2,
    acks_late=True,
)
def process_deferred_alert(
    self: Any,
    alert_data: dict[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    """Processa alerta deferido (lock NÃO foi adquirido).

    Aguarda o alerta primário ser processado, depois adiciona
    este alerta como evento adicional ao incidente existente.
    """
    redis = _get_sync_redis()
    lock_key = f"ninf:lock:{fingerprint}"

    # Se o lock ainda existe, o primário ainda não terminou → retry
    if redis.exists(lock_key):
        redis.close()
        logger.info(
            "Lock ainda ativo, reagendando | fingerprint=%s retry=%d",
            fingerprint,
            self.request.retries,
        )
        raise self.retry(countdown=settings.lock_retry_delay_seconds)

    redis.close()

    # Lock liberado → o incidente já existe, apenas incrementar
    sanitized = _sanitize_alert(alert_data)
    incident = asyncio.run(_async_increment_incident(fingerprint, sanitized))

    logger.info(
        "Alerta deferido processado | fingerprint=%s alerts=%d",
        fingerprint,
        incident["alert_count"],
    )
    return incident


@celery_app.task(
    name="app.workers.tasks.run_anomaly_check",
    acks_late=True,
)
def run_anomaly_check(
    item_id: str,
    host_id: str,
    current_value: float,
    historical_values: list[float],
) -> dict[str, Any]:
    """Executa Z-Score Robusto em um datapoint contra histórico.

    Chamado periodicamente pelo Celery Beat ou sob demanda.
    """
    import numpy as np

    from app.ml.anomaly import detect_single

    threshold = settings.anomaly_zscore_threshold

    if len(historical_values) < settings.anomaly_min_datapoints:
        return {
            "item_id": item_id,
            "is_anomaly": False,
            "reason": f"Dados insuficientes ({len(historical_values)}/{settings.anomaly_min_datapoints})",
        }

    history = np.array(historical_values, dtype=np.float64)
    is_anomaly, z_score, result = detect_single(current_value, history, threshold)

    return {
        "item_id": item_id,
        "host_id": host_id,
        "current_value": current_value,
        "z_score": round(z_score, 4),
        "median": round(result.median, 4),
        "mad": round(result.mad, 4),
        "threshold": threshold,
        "is_anomaly": is_anomaly,
    }


# -------------------------------------------------------------------
# Funções auxiliares (domínio) — serão migradas para um Repository
# quando o SQLAlchemy for integrado.
# -------------------------------------------------------------------


def _sanitize_alert(alert_data: dict[str, Any]) -> dict[str, Any]:
    """Pipeline de sanitização completa."""
    # Sanitiza campos textuais
    sanitized = sanitize_dict(alert_data)

    # Campos específicos que costumam carregar PII
    for field in ("trigger_description", "trigger_name", "host_ip"):
        if field in sanitized and isinstance(sanitized[field], str):
            sanitized[field] = sanitize(sanitized[field])

    return sanitized


async def _async_upsert_incident(
    fingerprint: str,
    alert_data: dict[str, Any],
) -> dict[str, Any]:
    """Cria ou atualiza incidente no PostgreSQL utilizando SQLAlchemy Async."""
    async with SessionLocal() as session:
        async with session.begin():
            # Check if incident already exists
            stmt = select(Incident).where(Incident.fingerprint == fingerprint)
            result = await session.execute(stmt)
            db_incident = result.scalar_one_or_none()

            now = datetime.now(timezone.utc)

            # Try to resolve Asset based on host_id
            asset_stmt = select(Asset).where(
                Asset.zabbix_host_id == alert_data.get("host_id")
            )
            asset_result = await session.execute(asset_stmt)
            db_asset = asset_result.scalar_one_or_none()
            asset_id = db_asset.id if db_asset else None

            if db_incident:
                # Update existing
                db_incident.alert_count += 1
                db_incident.last_seen = now
                db_incident.updated_at = now
                if asset_id:
                    db_incident.asset_id = asset_id
                action = "incremented"
            else:
                # Create new
                db_incident = Incident(
                    fingerprint=fingerprint,
                    title=alert_data.get("trigger_name", "Unknown"),
                    severity=int(alert_data.get("severity", 3)),
                    status="open",
                    host_id=alert_data.get("host_id", ""),
                    host_name=alert_data.get("host_name", ""),
                    trigger_id=alert_data.get("trigger_id", ""),
                    asset_id=asset_id,
                    alert_count=1,
                    first_seen=now,
                    last_seen=now,
                    sanitized_description=alert_data.get("trigger_description", ""),
                    tags=alert_data.get("tags", {}),
                )
                session.add(db_incident)
                action = "created"

            # Flush to get the ID and attributes
            await session.flush()

            # Construct response dict (must serialize datetime objects)
            incident_dict = {
                "id": db_incident.id,
                "fingerprint": db_incident.fingerprint,
                "title": db_incident.title,
                "severity": db_incident.severity,
                "status": db_incident.status,
                "host_id": db_incident.host_id,
                "host_name": db_incident.host_name,
                "trigger_id": db_incident.trigger_id,
                "asset_id": db_incident.asset_id,
                "alert_count": db_incident.alert_count,
                "first_seen": (
                    db_incident.first_seen.isoformat()
                    if db_incident.first_seen
                    else now.isoformat()
                ),
                "last_seen": (
                    db_incident.last_seen.isoformat()
                    if db_incident.last_seen
                    else now.isoformat()
                ),
                "sanitized_description": db_incident.sanitized_description or "",
                "tags": db_incident.tags or {},
                "action": action,
            }
            return incident_dict


async def _async_increment_incident(
    fingerprint: str,
    alert_data: dict[str, Any],
) -> dict[str, Any]:
    """Incrementa o contador de alertas de um incidente existente no PostgreSQL."""
    async with SessionLocal() as session:
        async with session.begin():
            stmt = select(Incident).where(Incident.fingerprint == fingerprint)
            result = await session.execute(stmt)
            db_incident = result.scalar_one_or_none()

            now = datetime.now(timezone.utc)

            if db_incident:
                db_incident.alert_count += 1
                db_incident.last_seen = now
                db_incident.updated_at = now

                # If asset_id is not set, try to resolve it
                if not db_incident.asset_id:
                    asset_stmt = select(Asset).where(
                        Asset.zabbix_host_id == alert_data.get("host_id")
                    )
                    asset_result = await session.execute(asset_stmt)
                    db_asset = asset_result.scalar_one_or_none()
                    if db_asset:
                        db_incident.asset_id = db_asset.id

                action = "incremented"
            else:
                # Fallback to creation if not found
                asset_stmt = select(Asset).where(
                    Asset.zabbix_host_id == alert_data.get("host_id")
                )
                asset_result = await session.execute(asset_stmt)
                db_asset = asset_result.scalar_one_or_none()
                asset_id = db_asset.id if db_asset else None

                db_incident = Incident(
                    fingerprint=fingerprint,
                    title=alert_data.get("trigger_name", "Unknown"),
                    severity=int(alert_data.get("severity", 3)),
                    status="open",
                    host_id=alert_data.get("host_id", ""),
                    host_name=alert_data.get("host_name", ""),
                    trigger_id=alert_data.get("trigger_id", ""),
                    asset_id=asset_id,
                    alert_count=1,
                    first_seen=now,
                    last_seen=now,
                    sanitized_description=alert_data.get("trigger_description", ""),
                    tags=alert_data.get("tags", {}),
                )
                session.add(db_incident)
                action = "created"

            await session.flush()

            incident_dict = {
                "id": db_incident.id,
                "fingerprint": db_incident.fingerprint,
                "title": db_incident.title,
                "severity": db_incident.severity,
                "status": db_incident.status,
                "host_id": db_incident.host_id,
                "host_name": db_incident.host_name,
                "trigger_id": db_incident.trigger_id,
                "asset_id": db_incident.asset_id,
                "alert_count": db_incident.alert_count,
                "first_seen": (
                    db_incident.first_seen.isoformat()
                    if db_incident.first_seen
                    else now.isoformat()
                ),
                "last_seen": (
                    db_incident.last_seen.isoformat()
                    if db_incident.last_seen
                    else now.isoformat()
                ),
                "sanitized_description": db_incident.sanitized_description or "",
                "tags": db_incident.tags or {},
                "action": action,
            }
            return incident_dict
