import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from redis import Redis
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.integrations.glpi import GLPIClient
from app.integrations.loki import LokiClient
from app.integrations.whatsapp import WhatsAppClient
from app.ml.analyzer import analyze_incident
from app.models import Asset, Incident
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_sync_redis() -> Redis:
    """Redis síncrono para o worker Celery."""
    return Redis.from_url(settings.redis_url, decode_responses=True)


def resolve_customer_name(h_name: str, tags_dict: dict[str, str]) -> str:
    for k in (
        "cliente",
        "client",
        "customer",
        "tenant",
        "Cliente",
        "Client",
        "Customer",
        "Tenant",
    ):
        if tags_dict and k in tags_dict and tags_dict[k]:
            return tags_dict[k]
    if "-" in h_name:
        parts = h_name.split("-")
        if len(parts) > 1:
            first = parts[0]
            if first.lower() not in (
                "wan",
                "lan",
                "srv",
                "web",
                "db",
                "app",
                "fw",
                "vpn",
                "core",
                "test",
            ):
                return first.upper()
    return "Outros"


def resolve_glpi_entity_id(customer_name: str) -> int:
    """Mapeia o nome do cliente para o ID da entidade GLPI."""
    name_lower = customer_name.lower()
    if "alupar" in name_lower:
        return 1
    if "tbe" in name_lower:
        return 2
    if "target" in name_lower:
        return 3
    if "ltb" in name_lower or "tosto" in name_lower:
        return 4
    if "bichara" in name_lower:
        return 7
    if "cavan" in name_lower:
        return 8
    if "nova energia" in name_lower or "novaenergia" in name_lower:
        return 9
    if "numen" in name_lower:
        return 10
    if "tne" in name_lower:
        return 11
    return 0  # Root Entity (Ness)


def resolve_glpi_category_id(alert_data: Dict[str, Any]) -> int:
    """Resolve o ID da categoria do GLPI com base nos dados do alerta.

    Se for um alerta de segurança (SOC, SIEM, Wazuh, etc.), retorna settings.glpi_security_category_id.
    Caso contrário (NOC, Zabbix infra), retorna settings.glpi_infra_category_id.
    """
    trigger_name = alert_data.get("trigger_name", "").lower()
    tags = alert_data.get("tags", {})

    # 1. Verificar se o assunto do gatilho contém termos de segurança
    security_keywords = [
        "secops",
        "soc",
        "wazuh",
        "siem",
        "seguranca",
        "segurança",
        "firewall",
        "intrusao",
        "intrusão",
        "malware",
        "virus",
        "phishing",
        "brute force",
        "bruteforce",
        "scan",
    ]
    if any(kw in trigger_name for kw in security_keywords):
        return settings.glpi_security_category_id

    # 2. Verificar chaves e valores das tags
    if tags:
        for k, v in tags.items():
            k_lower = str(k).lower()
            v_lower = str(v).lower()
            if any(
                kw in k_lower or kw in v_lower
                for kw in [
                    "soc",
                    "wazuh",
                    "siem",
                    "security",
                    "seguranca",
                    "segurança",
                ]
            ):
                return settings.glpi_security_category_id

    return settings.glpi_infra_category_id


async def _async_process_alert_v1(
    alert_data: Dict[str, Any], fingerprint: str
) -> Dict[str, Any]:
    # 1. Resolver o cliente do ativo
    host_name = alert_data.get("host_name", "")
    tags = alert_data.get("tags", {})
    customer_name = resolve_customer_name(host_name, tags)
    entity_id = resolve_glpi_entity_id(customer_name)

    logger.info(
        "Processando alerta v1 | Cliente: %s | Entity ID: %d", customer_name, entity_id
    )

    # 2. Executar análise IA estruturada
    analysis = await analyze_incident(
        incident_data=alert_data,
        customer_metadata={"customer_name": customer_name, "entity_id": entity_id},
    )
    logger.info("Análise IA gerada: %s", analysis.model_dump_json())

    # 3. Abrir chamado no GLPI
    glpi = GLPIClient()

    ticket_title = f"[AIOps] {alert_data.get('trigger_name', 'Alerta')}"
    ticket_content = f"""
<h2>Relatório AIOps — Triagem de Incidente</h2>
<hr/>
<p><b>Host:</b> {host_name} ({alert_data.get("host_ip", "Sem IP")})</p>
<p><b>Severidade do Alerta:</b> {alert_data.get("severity", "AVERAGE")}</p>
<p><b>Causa Provável:</b> {analysis.probable_cause}</p>
<p><b>Urgência de IA:</b> {analysis.urgency}</p>
<p><b>Isolamento Requerido:</b> {"Sim" if analysis.isolation_required else "Não"}</p>
<hr/>
<h3>Plano de Ação Executivo:</h3>
<p>{analysis.executive_action_plan}</p>
<h3>Plano de Ação Técnico:</h3>
<p>{analysis.technical_action_plan}</p>
<h3>Playbook Recomendado:</h3>
<p><code>{analysis.recommended_playbook}</code></p>
"""

    ticket_id = None
    try:
        await glpi.init_session()
        category_id = resolve_glpi_category_id(alert_data)
        glpi_res = await glpi.create_ticket(
            title=ticket_title,
            content=ticket_content,
            entity_id=entity_id,
            itilcategories_id=category_id,
        )
        if isinstance(glpi_res, list) and len(glpi_res) > 0:
            ticket_id = glpi_res[0].get("id")
        elif isinstance(glpi_res, dict):
            ticket_id = glpi_res.get("id")

        logger.info(
            "Ticket GLPI criado com ID: %s | Categoria ID: %s", ticket_id, category_id
        )

        if ticket_id:
            await glpi.add_comment(
                ticket_id=int(ticket_id),
                content="Chamado gerado automaticamente pela plataforma n.infraops AIOps.",
                private=True,
            )
    except Exception as e:
        logger.error(
            "Erro ao criar ticket no GLPI durante o processamento do alerta: %s", e
        )
    finally:
        await glpi.kill_session()

    # 4. WhatsApp: Notificar NOC
    if analysis.urgency in ("HIGH", "CRITICAL") or analysis.isolation_required:
        whatsapp = WhatsAppClient()
        recipient = settings.whatsapp_noc_group_id

        if recipient:
            wa_message = f"""🚨 *AIOps Alerta Crítico — {customer_name}*
━━━━━━━━━━━━━━━━━━━━━
*Host:* {host_name}
*Incidente:* {alert_data.get("trigger_name", "Trigger")}
*Causa Provável:* {analysis.probable_cause}
*Urgência:* {analysis.urgency}
*Isolamento Requerido:* {"⚠️ SIM" if analysis.isolation_required else "NÃO"}
━━━━━━━━━━━━━━━━━━━━━
*Plano Executivo:*
{analysis.executive_action_plan}

*Plano Técnico:*
{analysis.technical_action_plan}
━━━━━━━━━━━━━━━━━━━━━
🎫 *Chamado GLPI:* {ticket_id if ticket_id else "Não criado"}
"""
            try:
                await whatsapp.send_text_message(recipient=recipient, text=wa_message)
            except Exception as e:
                logger.error(
                    "Erro ao disparar mensagem de WhatsApp via Evolution API: %s", e
                )
        else:
            logger.warning(
                "NINF_WHATSAPP_NOC_GROUP_ID não configurado. Notificação do WhatsApp pulada."
            )

    # 4.5. Grafana Loki: Persistência de Inteligência Operacional (Com labels de baixa cardinalidade)
    try:
        loki = LokiClient()
        loki_labels = {
            "tenant_id": customer_name,
            "source": "aiops_engine",
            "severity": analysis.urgency.lower(),
        }
        loki_payload = {
            "alert": alert_data,
            "analysis": analysis.model_dump(),
            "ticket_id": ticket_id,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        await loki.send_json_log(
            tenant_id=customer_name, log_data=loki_payload, labels=loki_labels
        )
    except Exception as e:
        logger.error("Erro ao enviar logs estruturados para o Grafana Loki: %s", e)

    # 5. Persistir/Atualizar incidente no PostgreSQL local
    async with SessionLocal() as session:
        async with session.begin():
            stmt = select(Incident).where(Incident.fingerprint == fingerprint)
            result = await session.execute(stmt)
            db_incident = result.scalar_one_or_none()

            now = datetime.now(timezone.utc)

            asset_stmt = select(Asset).where(
                (Asset.zabbix_host_id == alert_data.get("host_id"))
                | (Asset.hostname == alert_data.get("host_name"))
                | (Asset.ip_address == alert_data.get("host_ip"))
            )
            asset_result = await session.execute(asset_stmt)
            db_asset = asset_result.scalar_one_or_none()
            asset_id = db_asset.id if db_asset else None

            if db_incident:
                db_incident.alert_count += 1
                db_incident.last_seen = now
                db_incident.updated_at = now
                if ticket_id:
                    db_incident.deskmanager_ticket_id = str(ticket_id)
            else:
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
                    deskmanager_ticket_id=str(ticket_id) if ticket_id else None,
                )
                session.add(db_incident)

            await session.flush()

            # 6. Publicar no Redis Pub/Sub para atualização em tempo real no Dashboard (SSE)
            try:
                severity_map = {
                    0: "not_classified",
                    1: "info",
                    2: "warning",
                    3: "average",
                    4: "high",
                    5: "disaster",
                }
                event_data = {
                    "id": str(db_incident.id),
                    "fingerprint": fingerprint,
                    "title": alert_data.get("trigger_name", "Unknown"),
                    "severity": severity_map.get(
                        int(alert_data.get("severity", 3)), "unknown"
                    ),
                    "severity_level": int(alert_data.get("severity", 3)),
                    "host_name": host_name,
                    "client": customer_name,
                    "tenant_id": customer_name.lower().strip(),
                    "status": "open",
                    "first_seen": now.isoformat(),
                    "last_seen": now.isoformat(),
                    "analysis": {
                        "probable_cause": getattr(analysis, "probable_cause", ""),
                        "urgency": getattr(analysis, "urgency", "AVERAGE"),
                        "isolation_required": getattr(
                            analysis, "isolation_required", False
                        ),
                        "executive_action_plan": getattr(
                            analysis, "executive_action_plan", ""
                        ),
                    },
                }
                redis_client = _get_sync_redis()
                redis_client.publish("ninf_incidents", json.dumps(event_data))
                redis_client.close()
                logger.info(
                    "Incidente publicado com sucesso no Redis Pub/Sub para o canal ninf_incidents."
                )
            except Exception as e:
                logger.error(f"Erro ao publicar incidente no Redis Pub/Sub: {e}")

            # 7. Disparar Web Push para stakeholders do tenant se for HIGH/CRITICAL ou isolamento urgente
            if analysis.urgency in ("HIGH", "CRITICAL") or analysis.isolation_required:
                try:
                    from app.integrations.webpush import notify_tenant_stakeholders

                    push_title = (
                        f"Alerta Crítico: {alert_data.get('trigger_name', 'Incidente')}"
                    )
                    push_body = f"Host {host_name} precisa de atenção urgente. IA sugere: {analysis.executive_action_plan[:100]}..."

                    # Cria loop de eventos se não houver um rodando na thread (caso do Celery worker)
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(
                            notify_tenant_stakeholders(
                                tenant_id=customer_name.lower().strip(),
                                title=push_title,
                                body=push_body,
                                incident_id=str(db_incident.id),
                                fingerprint=fingerprint,
                                severity=analysis.urgency.lower(),
                            )
                        )
                    except RuntimeError:
                        # Se não houver loop rodando na thread, roda de forma síncrona
                        asyncio.run(
                            notify_tenant_stakeholders(
                                tenant_id=customer_name.lower().strip(),
                                title=push_title,
                                body=push_body,
                                incident_id=str(db_incident.id),
                                fingerprint=fingerprint,
                                severity=analysis.urgency.lower(),
                            )
                        )
                except Exception as e:
                    logger.error(f"Erro ao disparar Web Push para stakeholders: {e}")

            return {
                "id": db_incident.id,
                "fingerprint": fingerprint,
                "ticket_id": ticket_id,
                "whatsapp_sent": analysis.urgency in ("HIGH", "CRITICAL")
                or analysis.isolation_required,
            }


@celery_app.task(
    bind=True,
    name="app.workers.alerts.process_alert_v1",
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def process_alert_v1(
    self: Any,
    alert_data: dict[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    """Processa alerta v1 (AIOps pipeline).

    Implementa deduplicação/inibição com chaves SHA-256 no Redis (`ninf-redis`)
    com TTL de 300 segundos.
    """
    redis = _get_sync_redis()
    inhibit_key = f"ninf:inhibit:{fingerprint}"

    if redis.exists(inhibit_key):
        logger.info(
            "Alerta DEDUPLICADO / INIBIDO | fingerprint=%s host=%s trigger=%s",
            fingerprint,
            alert_data.get("host_name"),
            alert_data.get("trigger_name"),
        )
        redis.close()
        return {"status": "deduplicated", "fingerprint": fingerprint}

    redis.set(inhibit_key, "1", ex=300)
    redis.close()

    try:
        logger.info(
            "Iniciando processamento AIOps | fingerprint=%s host=%s trigger=%s",
            fingerprint,
            alert_data.get("host_name"),
            alert_data.get("trigger_name"),
        )

        result = asyncio.run(_async_process_alert_v1(alert_data, fingerprint))
        return result

    except Exception as exc:
        try:
            redis_err = _get_sync_redis()
            redis_err.delete(inhibit_key)
            redis_err.close()
        except Exception:
            pass
        logger.exception("Falha ao processar alerta v1 AIOps: %s", exc)
        raise self.retry(exc=exc)
