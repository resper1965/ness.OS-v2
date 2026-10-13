import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from html import escape
from typing import Any, Dict
from uuid import uuid4

from celery.exceptions import Retry
from redis import Redis
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.integrations.glpi import GLPIClient, GLPIPermanentError, GLPITransientError
from app.integrations.loki import LokiClient
from app.integrations.whatsapp import WhatsAppClient
from app.integrations.zabbix import ZabbixClient
from app.ml.analyzer import analyze_incident
from app.models import Asset, Incident, IncidentAction
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
    name_lower = customer_name.lower().strip()
    if name_lower in ("alupar pe", "alupar-pe"):
        return 5
    if name_lower in ("alupar co", "alupar-co"):
        return 6
    if name_lower in ("alupar", "alupar investimento s.a."):
        return 1
    if name_lower == "tbe":
        return 2
    if name_lower in ("target", "target trading"):
        return 3
    if name_lower in ("ltb", "leite tosto", "leite tosto e barros adv ass"):
        return 4
    if name_lower == "bichara":
        return 7
    if name_lower == "cavan":
        return 8
    if name_lower in ("nova energia", "novaenergia"):
        return 9
    if name_lower in ("numen", "numen it"):
        return 10
    if name_lower == "tne":
        return 11
    if name_lower in ("ness", "ness processos e tecnologia ltda."):
        return 0
    raise ValueError("Cliente sem entidade GLPI mapeada; ticket recusado")


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


def customer_from_hostgroups(groups: list[dict[str, str]]) -> str | None:
    candidates = {}
    for group in groups:
        name = group.get("name", "")
        match = re.match(r"^\[\s*([^\]]+?)\s*\]", name)
        customer = match.group(1).strip() if match else None
        if name in ("Zabbix servers", "UAT sintético"):
            customer = "Ness"
        if customer:
            try:
                candidates[resolve_glpi_entity_id(customer)] = customer
            except ValueError:
                continue
    if len(candidates) > 1:
        candidates.pop(0, None)  # Generic monitoring group is not a customer.
    if set(candidates) in ({1, 5}, {1, 6}):
        candidates.pop(1)
    if len(candidates) > 1:
        raise ValueError("Host associado a clientes distintos; ticket recusado")
    return next(iter(candidates.values()), None)


async def resolve_alert_customer(alert_data: Dict[str, Any]) -> str:
    host_id = alert_data.get("host_id")
    if host_id:
        hosts = await ZabbixClient()._call(
            "host.get",
            {"hostids": [host_id], "output": ["hostid"], "selectHostGroups": ["name"]},
        )
        if len(hosts) != 1:
            raise ValueError("Host Zabbix não encontrado ou não autorizado")
        customer = customer_from_hostgroups(hosts[0].get("hostgroups", []))
        if customer:
            return customer
    return resolve_customer_name(
        alert_data.get("host_name", ""), alert_data.get("tags", {})
    )


async def ensure_glpi_ticket(
    glpi: GLPIClient,
    *,
    fingerprint: str,
    entity_id: int,
    category_id: int,
    title: str,
    content: str,
    linked_item: dict | None = None,
) -> tuple[int, bool]:
    """Return the single GLPI ticket for a fingerprint, creating it if absent."""
    marker = f"[n.infraops:{fingerprint}]"
    await glpi.change_active_entity(entity_id)
    existing_id = await glpi.find_ticket_by_name_marker(marker, entity_id)
    if existing_id is not None:
        return existing_id, False

    response = await glpi.create_ticket(
        title=f"{marker} {title}",
        content=content,
        entity_id=entity_id,
        itilcategories_id=category_id,
        **({"linked_item": linked_item} if linked_item else {}),
    )
    if isinstance(response, list) and response:
        ticket_id = response[0].get("id")
    elif isinstance(response, dict):
        ticket_id = response.get("id")
    else:
        ticket_id = None
    if not isinstance(ticket_id, int) or ticket_id <= 0:
        raise RuntimeError("GLPI não retornou um ID de ticket válido")

    await glpi.add_comment(
        ticket_id=ticket_id,
        content="Chamado gerado automaticamente pela plataforma n.infraops AIOps.",
        private=True,
    )
    return ticket_id, True


async def lookup_glpi_asset(host_id: str, customer: str) -> dict | None:
    async with SessionLocal() as session:
        asset = (
            await session.execute(
                select(Asset).where(
                    Asset.zabbix_host_id == host_id,
                    Asset.customer_id == customer.lower().strip(),
                )
            )
        ).scalar_one_or_none()
        if asset and asset.tags.get("glpi_item_id"):
            return {
                "itemtype": asset.tags["glpi_itemtype"],
                "id": asset.tags["glpi_item_id"],
            }
    return None


def build_glpi_ticket_content(alert_data: Dict[str, Any], analysis: Any) -> str:
    """Render untrusted alert and analysis text inside the GLPI HTML body."""
    host_name = escape(str(alert_data.get("host_name", "")))
    host_ip = escape(str(alert_data.get("host_ip", "Sem IP")))
    severity = escape(str(alert_data.get("severity", "AVERAGE")))
    cause = escape(str(analysis.probable_cause))
    urgency = escape(str(analysis.urgency))
    executive_plan = escape(str(analysis.executive_action_plan))
    technical_plan = escape(str(analysis.technical_action_plan))
    playbook = escape(str(analysis.recommended_playbook))
    return f"""
<h2>Relatório AIOps — Triagem de Incidente</h2>
<hr/>
<p><b>Host:</b> {host_name} ({host_ip})</p>
<p><b>Severidade do Alerta:</b> {severity}</p>
<p><b>Causa Provável:</b> {cause}</p>
<p><b>Urgência de IA:</b> {urgency}</p>
<p><b>Isolamento Requerido:</b> {"Sim" if analysis.isolation_required else "Não"}</p>
<hr/>
<h3>Plano de Ação Executivo:</h3>
<p>{executive_plan}</p>
<h3>Plano de Ação Técnico:</h3>
<p>{technical_plan}</p>
<h3>Playbook Recomendado:</h3>
<p><code>{playbook}</code></p>
"""


async def _async_process_alert_v1(
    alert_data: Dict[str, Any], fingerprint: str
) -> Dict[str, Any]:
    if str(alert_data.get("status", "PROBLEM")).upper() in {"RESOLVED", "OK"}:
        return await _async_process_recovery(alert_data, fingerprint)

    # 1. Resolver o cliente do ativo
    host_name = alert_data.get("host_name", "")
    customer_name = await resolve_alert_customer(alert_data)
    entity_id = resolve_glpi_entity_id(customer_name)
    linked_item = await lookup_glpi_asset(alert_data.get("host_id", ""), customer_name)

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
    ticket_content = build_glpi_ticket_content(alert_data, analysis)

    ticket_id = None
    ticket_created = False
    glpi_error = None
    try:
        await glpi.init_session()
        category_id = resolve_glpi_category_id(alert_data)
        ticket_id, ticket_created = await ensure_glpi_ticket(
            glpi,
            fingerprint=fingerprint,
            entity_id=entity_id,
            category_id=category_id,
            title=ticket_title,
            content=ticket_content,
            linked_item=linked_item,
        )
        logger.info(
            "Ticket GLPI %s com ID: %s | Categoria ID: %s",
            "criado" if ticket_created else "reutilizado",
            ticket_id,
            category_id,
        )
    except Exception as e:
        glpi_error = e
        logger.error(
            "Erro ao criar ticket no GLPI durante o processamento do alerta: %s", e
        )
    finally:
        await glpi.kill_session()

    # 4. WhatsApp: Notificar NOC
    notify = (
        settings.alert_notifications_enabled
        and glpi_error is None
        and (analysis.urgency in ("HIGH", "CRITICAL") or analysis.isolation_required)
    )
    whatsapp_sent = False
    if notify:
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
                whatsapp_sent = True
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
            incident_created = db_incident is None
            previous_ticket_id = (
                db_incident.deskmanager_ticket_id if db_incident else None
            )

            now = datetime.now(timezone.utc)

            asset_stmt = select(Asset).where(
                Asset.zabbix_host_id == alert_data.get("host_id", ""),
                Asset.customer_id == customer_name.lower().strip(),
            )
            asset_result = await session.execute(asset_stmt)
            db_asset = asset_result.scalar_one_or_none()
            asset_id = db_asset.id if db_asset else None

            if db_incident:
                db_incident.asset_id = asset_id
                previous_event = (db_incident.tags or {}).get("ninf_zabbix_event_id")
                if previous_event != str(alert_data.get("event_id", "")):
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

            db_incident.tags = {
                **(db_incident.tags or {}),
                "ninf_customer_name": customer_name,
                "ninf_zabbix_event_id": str(alert_data.get("event_id", "")),
                "ninf_zabbix_status": (db_incident.tags or {}).get(
                    "ninf_zabbix_status", "problem"
                ),
            }
            await session.flush()
            if incident_created:
                session.add(
                    IncidentAction(
                        incident_id=db_incident.id,
                        actor_source="zabbix",
                        action="incident_created",
                        new_status=db_incident.status,
                        new_assignee_id=db_incident.assigned_user_id,
                        note=f"event={alert_data.get('event_id', '')}",
                    )
                )
            if glpi_error is not None:
                session.add(
                    IncidentAction(
                        incident_id=db_incident.id,
                        actor_source="glpi",
                        action="ticket_failed",
                        previous_status=db_incident.status,
                        new_status=db_incident.status,
                        previous_assignee_id=db_incident.assigned_user_id,
                        new_assignee_id=db_incident.assigned_user_id,
                        note=f"error={type(glpi_error).__name__}",
                    )
                )
            elif ticket_id and (
                ticket_created or str(ticket_id) != str(previous_ticket_id)
            ):
                session.add(
                    IncidentAction(
                        incident_id=db_incident.id,
                        actor_source="glpi",
                        action="ticket_created" if ticket_created else "ticket_reused",
                        previous_status=db_incident.status,
                        new_status=db_incident.status,
                        previous_assignee_id=db_incident.assigned_user_id,
                        new_assignee_id=db_incident.assigned_user_id,
                        note=f"ticket={ticket_id} entity={entity_id}",
                    )
                )

            # Capture persisted values before the session closes.
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
                "status": db_incident.status,
                "source_status": db_incident.tags["ninf_zabbix_status"],
                "ticket_id": db_incident.deskmanager_ticket_id,
                "pipeline_stage": (
                    "resolved"
                    if db_incident.status == "resolved"
                    else (
                        "ticket_opened"
                        if db_incident.deskmanager_ticket_id
                        else "incident_created"
                    )
                ),
                "alert_count": db_incident.alert_count,
                "first_seen": db_incident.first_seen.isoformat(),
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

            # 7. Disparar Web Push para stakeholders do tenant se for HIGH/CRITICAL ou isolamento urgente
            if notify:
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

            result_data = {
                "id": db_incident.id,
                "fingerprint": fingerprint,
                "ticket_id": ticket_id,
                "whatsapp_sent": whatsapp_sent,
            }

    # A failed commit must never announce an incident that was not persisted.
    _publish_incident_event(event_data)

    # Commit the local incident even when GLPI is unavailable, then let Celery retry.
    if glpi_error is not None:
        raise glpi_error
    return result_data


async def _async_process_recovery(
    alert_data: Dict[str, Any], fingerprint: str
) -> Dict[str, Any]:
    """Record Zabbix recovery; GLPI remains authoritative for ticket resolution."""
    async with SessionLocal() as session:
        async with session.begin():
            incident = (
                await session.execute(
                    select(Incident)
                    .where(Incident.fingerprint == fingerprint)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if incident is None:
                raise LookupError("Problem incident has not been persisted yet")
            tags = incident.tags or {}
            if (
                str(tags.get("ninf_zabbix_event_id")) != str(alert_data.get("event_id"))
                or incident.host_id != str(alert_data.get("host_id"))
                or incident.trigger_id != str(alert_data.get("trigger_id"))
            ):
                raise ValueError("Recovery does not match original Zabbix event")
            result = {
                "id": incident.id,
                "fingerprint": fingerprint,
                "ticket_id": incident.deskmanager_ticket_id,
                "status": "source_recovered",
            }
            if tags.get("ninf_zabbix_status") == "resolved":
                return result
            now = datetime.now(timezone.utc)
            incident.tags = {
                **tags,
                "ninf_zabbix_status": "resolved",
                "ninf_zabbix_recovered_at": now.isoformat(),
            }
            incident.last_seen = now
            incident.updated_at = now
            session.add(
                IncidentAction(
                    incident_id=incident.id,
                    actor_source="zabbix",
                    action="zabbix_recovered",
                    previous_status=incident.status,
                    new_status=incident.status,
                    previous_assignee_id=incident.assigned_user_id,
                    new_assignee_id=incident.assigned_user_id,
                    note=f"event={alert_data.get('event_id')}",
                )
            )
            event_data = {
                "id": str(incident.id),
                "fingerprint": fingerprint,
                "tenant_id": tags.get("ninf_customer_name", "").lower().strip(),
                "status": incident.status,
                "ticket_id": incident.deskmanager_ticket_id,
                "source_status": "resolved",
                "source_recovered_at": now.isoformat(),
            }
    _publish_incident_event(event_data)
    return result


async def _has_persisted_inhibition_completion(
    fingerprint: str, *, recovery: bool
) -> bool:
    """Check durable completion before treating a Redis inhibition as a duplicate."""
    async with SessionLocal() as session:
        statement = select(Incident.id).where(Incident.fingerprint == fingerprint)
        if recovery:
            statement = statement.where(
                Incident.tags["ninf_zabbix_status"].astext == "resolved"
            )
        return (await session.execute(statement)).scalar_one_or_none() is not None


def _publish_incident_event(event_data: dict) -> None:
    redis_client = None
    try:
        redis_client = _get_sync_redis()
        redis_client.publish("ninf_incidents", json.dumps(event_data))
    except Exception as exc:
        logger.warning(
            "Persisted incident could not be published: %s", type(exc).__name__
        )
    finally:
        if redis_client is not None:
            try:
                redis_client.close()
            except Exception:
                logger.warning("Could not close incident publisher")


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
    recovery = str(alert_data.get("status", "PROBLEM")).upper() in {"RESOLVED", "OK"}
    inhibit_key = f"ninf:inhibit:{fingerprint}{':recovery' if recovery else ''}"
    inhibit_token = uuid4().hex
    acquired = False

    try:
        redis = _get_sync_redis()
        try:
            acquired = bool(redis.set(inhibit_key, inhibit_token, ex=300, nx=True))
        finally:
            redis.close()
        if not acquired:
            if not asyncio.run(
                _has_persisted_inhibition_completion(fingerprint, recovery=recovery)
            ):
                logger.info(
                    "Inibição sem conclusão persistida; reagendando | fingerprint=%s",
                    fingerprint,
                )
                raise self.retry(countdown=settings.lock_retry_delay_seconds)
            logger.info(
                "Alerta DEDUPLICADO / INIBIDO | fingerprint=%s host=%s trigger=%s",
                fingerprint,
                alert_data.get("host_name"),
                alert_data.get("trigger_name"),
            )
            return {"status": "deduplicated", "fingerprint": fingerprint}

        logger.info(
            "Iniciando processamento AIOps | fingerprint=%s host=%s trigger=%s",
            fingerprint,
            alert_data.get("host_name"),
            alert_data.get("trigger_name"),
        )

        result = asyncio.run(_async_process_alert_v1(alert_data, fingerprint))
        return result

    except Retry:
        raise
    except Exception as exc:
        try:
            if acquired:
                redis_err = _get_sync_redis()
                try:
                    # A slow attempt must not delete a newer worker's inhibition.
                    redis_err.eval(
                        "if redis.call('get', KEYS[1]) == ARGV[1] then "
                        "return redis.call('del', KEYS[1]) else return 0 end",
                        1,
                        inhibit_key,
                        inhibit_token,
                    )
                finally:
                    redis_err.close()
        except Exception:
            pass
        if isinstance(exc, GLPIPermanentError):
            logger.error("GLPI permission denied; incident retained for manual repair")
            return {
                "status": "blocked",
                "fingerprint": fingerprint,
                "reason": "glpi_permission",
            }
        if isinstance(exc, GLPITransientError):
            countdown = min(30 * 2 ** min(self.request.retries, 5), 900)
            logger.warning("GLPI temporarily unavailable; retry scheduled")
            raise self.retry(exc=exc, countdown=countdown, max_retries=12)
        logger.exception("Falha ao processar alerta v1 AIOps: %s", exc)
        raise self.retry(exc=exc)
