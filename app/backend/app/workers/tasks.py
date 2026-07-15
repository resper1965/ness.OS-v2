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

        # --- 4. Notificar n8n (Ticket + WhatsApp) ---
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
    def resolve_customer_name(h_name: str, tags_dict: dict[str, str]) -> str:
        for k in ("cliente", "client", "customer", "tenant", "Cliente", "Client", "Customer", "Tenant"):
            if tags_dict and k in tags_dict and tags_dict[k]:
                return tags_dict[k]
        if "-" in h_name:
            parts = h_name.split("-")
            if len(parts) > 1:
                first = parts[0]
                if first.lower() not in ("wan", "lan", "srv", "web", "db", "app", "fw", "vpn", "core", "test"):
                    return first.upper()
        if "wan-core" in h_name.lower() or "web-server" in h_name.lower():
            return "Ness"
        return "Outros"

    async with SessionLocal() as session:
        async with session.begin():
            # Check if incident already exists
            stmt = select(Incident).where(Incident.fingerprint == fingerprint)
            result = await session.execute(stmt)
            db_incident = result.scalar_one_or_none()

            now = datetime.now(timezone.utc)

            # Try to resolve Asset based on host_id, hostname, or IP address
            asset_stmt = select(Asset).where(
                (Asset.zabbix_host_id == alert_data.get("host_id")) |
                (Asset.hostname == alert_data.get("host_name")) |
                (Asset.ip_address == alert_data.get("host_ip"))
            )
            asset_result = await session.execute(asset_stmt)
            db_asset = asset_result.scalar_one_or_none()
            
            if db_asset:
                # Se o ativo foi pareado pelo hostname/IP mas não tinha o ID do Zabbix, atualiza
                if not db_asset.zabbix_host_id or db_asset.zabbix_host_id == f"rmm_{db_asset.rmm_device_id}":
                    db_asset.zabbix_host_id = alert_data.get("host_id")
            elif alert_data.get("host_id"):
                customer_name = resolve_customer_name(alert_data.get("host_name", ""), alert_data.get("tags", {}))
                db_asset = Asset(
                    zabbix_host_id=alert_data.get("host_id"),
                    hostname=alert_data.get("host_name"),
                    ip_address=alert_data.get("host_ip"),
                    customer_name=customer_name,
                    customer_id=customer_name.lower(),
                    status="active",
                )
                session.add(db_asset)
                await session.flush()
                
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
                "first_seen": db_incident.first_seen.isoformat() if db_incident.first_seen else now.isoformat(),
                "last_seen": db_incident.last_seen.isoformat() if db_incident.last_seen else now.isoformat(),
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
                        (Asset.zabbix_host_id == alert_data.get("host_id")) |
                        (Asset.hostname == alert_data.get("host_name")) |
                        (Asset.ip_address == alert_data.get("host_ip"))
                    )
                    asset_result = await session.execute(asset_stmt)
                    db_asset = asset_result.scalar_one_or_none()
                    if db_asset:
                        db_incident.asset_id = db_asset.id
                        if not db_asset.zabbix_host_id or db_asset.zabbix_host_id == f"rmm_{db_asset.rmm_device_id}":
                            db_asset.zabbix_host_id = alert_data.get("host_id")

                action = "incremented"
            else:
                # Fallback to creation if not found
                asset_stmt = select(Asset).where(
                    (Asset.zabbix_host_id == alert_data.get("host_id")) |
                    (Asset.hostname == alert_data.get("host_name")) |
                    (Asset.ip_address == alert_data.get("host_ip"))
                )
                asset_result = await session.execute(asset_stmt)
                db_asset = asset_result.scalar_one_or_none()
                asset_id = db_asset.id if db_asset else None
                if db_asset and (not db_asset.zabbix_host_id or db_asset.zabbix_host_id == f"rmm_{db_asset.rmm_device_id}"):
                    db_asset.zabbix_host_id = alert_data.get("host_id")

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
                "first_seen": db_incident.first_seen.isoformat() if db_incident.first_seen else now.isoformat(),
                "last_seen": db_incident.last_seen.isoformat() if db_incident.last_seen else now.isoformat(),
                "sanitized_description": db_incident.sanitized_description or "",
                "tags": db_incident.tags or {},
                "action": action,
            }
            return incident_dict


@celery_app.task(
    name="app.workers.tasks.sync_assets_from_rmm",
    acks_late=True,
)
def sync_assets_from_rmm() -> dict[str, Any]:
    """Sincroniza ativos do Atera RMM para a tabela n_infraops_assets local."""
    from app.integrations.atera import AteraClient
    from app.models import Asset, AssetType, RmmProvider, AssetStatus
    
    if not settings.atera_api_key:
        logger.warning("NINF_ATERA_API_KEY não configurada. Pulando sincronização de ativos.")
        return {"status": "skipped", "reason": "API key missing"}

    client = AteraClient(api_key=settings.atera_api_key)
    
    try:
        # 1. Buscar todos os agentes do Atera RMM
        agents = asyncio.run(client.list_agents())
        logger.info(f"Sincronizando {len(agents)} ativos do Atera RMM...")
        
        # 2. Upsert no banco de dados local
        async def _db_upsert():
            async with SessionLocal() as session:
                async with session.begin():
                    updated_count = 0
                    created_count = 0
                    
                    for agent in agents:
                        device_id = str(agent.get("AgentID"))
                        hostname = agent.get("MachineName") or agent.get("AgentName", "")
                        ip_address = agent.get("IpAddresses") or agent.get("PublicIP", "")
                        customer_name = agent.get("CustomerName", "")
                        os_val = agent.get("OS") or agent.get("OSType", "")
                        
                        # Determinar tipo
                        if "windows" in (os_val or "").lower():
                            asset_type = AssetType.WINDOWS
                        else:
                            asset_type = AssetType.LINUX
                            
                        # Determinar status
                        status = AssetStatus.ACTIVE if agent.get("Online") or agent.get("OnlineStatus") == "Online" else AssetStatus.ACTIVE
                        
                        # Procurar se já existe por rmm_device_id ou hostname
                        stmt = select(Asset).where(
                            (Asset.rmm_device_id == device_id) |
                            (Asset.hostname == hostname)
                        )
                        result = await session.execute(stmt)
                        db_asset = result.scalar_one_or_none()
                        
                        if db_asset:
                            # Atualiza metadados
                            db_asset.rmm_device_id = device_id
                            db_asset.hostname = hostname
                            db_asset.ip_address = ip_address if ip_address else db_asset.ip_address
                            db_asset.customer_name = customer_name
                            db_asset.os_version = os_val
                            db_asset.rmm_provider = RmmProvider.ATERA
                            db_asset.updated_at = datetime.now(timezone.utc)
                            updated_count += 1
                        else:
                            # Cria novo
                            db_asset = Asset(
                                zabbix_host_id=f"rmm_{device_id}", # fallback provisório até ser pareado pelo alerta
                                hostname=hostname,
                                ip_address=ip_address if ip_address else None,
                                asset_type=asset_type,
                                status=status,
                                rmm_provider=RmmProvider.ATERA,
                                rmm_device_id=device_id,
                                os_version=os_val,
                                customer_name=customer_name,
                                customer_id=customer_name.lower() if customer_name else None,
                            )
                            session.add(db_asset)
                            created_count += 1
                            
                    return created_count, updated_count

        created, updated = asyncio.run(_db_upsert())
        logger.info(f"Sincronização de ativos concluída: {created} criados, {updated} atualizados.")
        return {"status": "success", "created": created, "updated": updated}
        
    except Exception as exc:
        logger.exception("Falha ao sincronizar ativos do RMM: %s", exc)
        return {"status": "failed", "error": str(exc)}


@celery_app.task(
    name="app.workers.tasks.process_ticket_resolution",
    acks_late=True,
)
def process_ticket_resolution(
    ticket_id: str,
    solution_text: str = "",
) -> dict[str, Any]:
    """Processa a resolução do ticket vinda do GLPI.
    
    1. Atualiza o status do incidente no PostgreSQL para 'resolved'.
    2. Enriquece o Post-Mortem com a solução humana e gera novos embeddings.
    3. Envia solicitação de fechamento/reconhecimento do alerta no Zabbix/Keep.
    """
    logger.info(
        "Iniciando processamento de resolução | ticket_id=%s",
        ticket_id,
    )
    
    from app.models import Incident, IncidentReport
    from app.integrations.gemini import generate_embedding
    from app.integrations.zabbix import ZabbixClient
    import asyncio
    
    async def _db_resolve():
        async with SessionLocal() as session:
            async with session.begin():
                # 1. Localiza o incidente
                stmt = select(Incident).where(Incident.deskmanager_ticket_id == ticket_id)
                result = await session.execute(stmt)
                db_incident = result.scalar_one_or_none()
                
                if not db_incident:
                    logger.warning("Nenhum incidente local encontrado com ticket_id=%s", ticket_id)
                    return None
                
                # Atualiza status
                db_incident.status = "resolved"
                db_incident.updated_at = datetime.now(timezone.utc)
                
                # 2. Localiza o relatório correspondente (Post-Mortem)
                report_stmt = select(IncidentReport).where(IncidentReport.deskmanager_ticket_id == ticket_id)
                report_result = await session.execute(report_stmt)
                db_report = report_result.scalar_one_or_none()
                
                if db_report:
                    # Enriquecer markdown com a solução humana
                    solution_md = f"\n\n## 🛠️ Solução Realizada (Humana)\n- {solution_text}\n"
                    db_report.markdown_report += solution_md
                    db_report.root_cause += f"\n\n[Solução Humana]: {solution_text}"
                    db_report.corrective_actions.append(f"Solução aplicada: {solution_text}")
                    
                    # Re-gerar embedding vetorial
                    new_embed = generate_embedding(db_report.markdown_report)
                    db_report.embedding = new_embed
                    logger.info("Relatório Post-Mortem enriquecido com a solução humana e re-indexado via pgvector.")
                
                return {
                    "fingerprint": db_incident.fingerprint,
                    "trigger_id": db_incident.trigger_id,
                    "host_id": db_incident.host_id,
                    "title": db_incident.title,
                }
                
    result_data = asyncio.run(_db_resolve())
    
    if not result_data:
        return {"status": "not_found", "ticket_id": ticket_id}
        
    # 3. Fechar alerta no Zabbix/Keep
    trigger_id = result_data.get("trigger_id")
    zabbix_status = "skipped"
    if trigger_id:
        try:
            zabbix = ZabbixClient()
            # Chama o método de reconhecer/fechar a trigger no Zabbix
            z_result = asyncio.run(zabbix.acknowledge_trigger(trigger_id, f"Resolvido automaticamente via GLPI Ticket {ticket_id}. Solução: {solution_text}"))
            zabbix_status = "success" if z_result else "failed"
        except Exception as e:
            logger.error("Falha ao reconhecer trigger no Zabbix: %s", e)
            zabbix_status = f"failed: {str(e)}"
            
    return {
        "status": "success",
        "ticket_id": ticket_id,
        "fingerprint": result_data.get("fingerprint"),
        "zabbix_status": zabbix_status,
    }


