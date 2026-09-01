# -------------------------------------------------------
# n.infraops — Task Celery: Geração de Post-Mortem
# -------------------------------------------------------
"""
Task que consolida métricas + logs, chama o Gemini 2.5 Flash
e gera o relatório pós-incidente em Markdown.

Pipeline completo:
  1. Buscar métricas do TimescaleDB (últimas 24h do host).
  2. Buscar logs sanitizados relacionados ao trigger.
  3. (Opcional) Buscar incidentes similares via pgvector.
  4. Montar prompt estruturado para o Gemini.
  5. Chamar Gemini → receber Markdown.
  6. Persistir relatório em `incident_reports`.
  7. Enviar ao n8n → DeskManager (Interação Interna).
"""

import asyncio
import logging
from typing import Any

from sqlalchemy import text

from app.config import get_settings
from app.core.sanitizer import sanitize
from app.database import SessionLocal
from app.models import IncidentReport
from app.integrations.gemini import generate_postmortem, generate_embedding
from app.integrations.n8n import notify_postmortem_ready
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


async def _async_generate_postmortem_report(
    incident_data: dict[str, Any],
    deskmanager_ticket_id: str | None = None,
) -> dict[str, Any]:
    # Resolvendo o nome do cliente
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
        if "wan-core" in h_name.lower() or "web-server" in h_name.lower():
            return "Ness"
        return "Outros"

    fingerprint = incident_data.get("fingerprint", "?")

    # Injetar ticket_id no contexto do incidente
    incident_data["deskmanager_ticket_id"] = deskmanager_ticket_id

    # Garantir que o incidente existe na tabela n_infraops_incidents antes de salvar o relatório (foreign key constraint)
    session = SessionLocal()
    try:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.models import Incident

        stmt = (
            select(Incident)
            .options(selectinload(Incident.asset))
            .where(Incident.fingerprint == fingerprint)
        )
        result = await session.execute(stmt)
        db_incident = result.scalar_one_or_none()
        if not db_incident:
            logger.info(
                "Criando incidente inexistente no banco de dados para postmortem | fingerprint=%s",
                fingerprint,
            )

            raw_severity = incident_data.get("severity", 3)
            if isinstance(raw_severity, str):
                sev_map = {
                    "disaster": 5,
                    "critical": 5,
                    "high": 4,
                    "average": 3,
                    "warning": 2,
                    "information": 1,
                    "info": 1,
                    "not_classified": 0,
                }
                severity_val = sev_map.get(raw_severity.lower(), 3)
            else:
                try:
                    severity_val = int(raw_severity)
                except (ValueError, TypeError):
                    severity_val = 3

            db_incident = Incident(
                fingerprint=fingerprint,
                title=incident_data.get("title", "Incidente Sem Título"),
                severity=severity_val,
                host_id=incident_data.get("host_id", ""),
                host_name=incident_data.get("host_name", ""),
                trigger_id=incident_data.get("trigger_id", ""),
                sanitized_description=incident_data.get("trigger_description", ""),
                deskmanager_ticket_id=deskmanager_ticket_id,
            )
            session.add(db_incident)
            await session.commit()

        # Injetar dados do cliente e host reais do banco
        incident_data["host_name"] = db_incident.host_name or incident_data.get(
            "host_name", "?"
        )
        if db_incident.asset and db_incident.asset.customer_name:
            incident_data["customer_name"] = db_incident.asset.customer_name
        else:
            incident_data["customer_name"] = resolve_customer_name(
                incident_data["host_name"], incident_data.get("tags", {})
            )
    except Exception as exc:
        await session.rollback()
        logger.error("Falha ao garantir existencia do incidente no banco: %s", exc)
        incident_data["customer_name"] = resolve_customer_name(
            incident_data.get("host_name", "?"), incident_data.get("tags", {})
        )
    finally:
        try:
            await session.rollback()
        except Exception:
            pass
        await session.close()

    # --- 1. Buscar métricas do TimescaleDB ---
    metrics = await _async_fetch_host_metrics(
        host_id=incident_data.get("host_id", ""),
        hours=24,
    )

    # --- 2. Buscar logs relacionados (já sanitizados) ---
    logs = _fetch_related_logs(
        host_id=incident_data.get("host_id", ""),
        trigger_id=incident_data.get("trigger_id", ""),
    )

    # --- 3. Buscar incidentes similares via pgvector ---
    similar = await _async_fetch_similar_incidents(
        title=incident_data.get("title", ""),
        description=incident_data.get("sanitized_description", "")
        or incident_data.get("trigger_description", ""),
        fingerprint=fingerprint,
    )

    # --- 4+5. Chamar Gemini ---
    report = generate_postmortem(
        incident=incident_data,
        metrics=metrics,
        related_logs=logs,
        similar_incidents=similar,
    )

    # --- 6. Persistir no PostgreSQL ---
    await _async_save_report(report.model_dump(mode="json"))

    # --- 7. Enviar ao n8n → DeskManager ---
    n8n_result = notify_postmortem_ready(report)

    logger.info(
        "Post-mortem concluído | fingerprint=%s tokens=%d+%d",
        fingerprint,
        report.prompt_tokens,
        report.completion_tokens,
    )

    return {
        "fingerprint": fingerprint,
        "deskmanager_ticket_id": deskmanager_ticket_id,
        "summary": report.summary,
        "root_cause": report.root_cause,
        "tokens_used": report.prompt_tokens + report.completion_tokens,
        "n8n_status": "ok" if "error" not in n8n_result else "failed",
    }


@celery_app.task(
    bind=True,
    name="app.workers.postmortem.generate_postmortem_report",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
    queue="ml",
)
def generate_postmortem_report(
    self: Any,
    incident_data: dict[str, Any],
    deskmanager_ticket_id: str | None = None,
) -> dict[str, Any]:
    """Gera relatório pós-incidente completo via Gemini.

    Args:
        incident_data: Dict do incidente consolidado (já sanitizado).
        deskmanager_ticket_id: ID do ticket no DeskManager (retornado pelo n8n).

    Returns:
        Dict com metadados do relatório gerado.
    """
    fingerprint = incident_data.get("fingerprint", "?")

    try:
        logger.info(
            "Iniciando geração de post-mortem | fingerprint=%s ticket=%s",
            fingerprint,
            deskmanager_ticket_id,
        )

        return asyncio.run(
            _async_generate_postmortem_report(
                incident_data=incident_data,
                deskmanager_ticket_id=deskmanager_ticket_id,
            )
        )

    except Exception as exc:
        logger.exception(
            "Falha ao gerar post-mortem | fingerprint=%s: %s",
            fingerprint,
            exc,
        )
        raise self.retry(exc=exc)


# -------------------------------------------------------------------
# Funções auxiliares (STUBS — serão substituídas por queries reais
# quando SQLAlchemy + TimescaleDB forem integrados)
# -------------------------------------------------------------------


async def _async_fetch_host_metrics(
    host_id: str,
    hours: int = 24,
) -> list[dict[str, Any]]:
    """Busca métricas agregadas do TimescaleDB para o host."""
    session = SessionLocal()
    try:
        query = text("""
            SELECT time_bucket('5 minutes', ts) AS bucket, item_key, AVG(value) AS avg_value
            FROM n_infraops_metrics
            WHERE host_id = :host_id AND ts > NOW() - CAST(:hours || ' hours' AS INTERVAL)
            GROUP BY bucket, item_key
            ORDER BY bucket ASC
        """)
        result = await session.execute(query, {"host_id": host_id, "hours": hours})
        return [
            {
                "timestamp": row.bucket.isoformat() if row.bucket else "",
                "item_key": row.item_key,
                "value": float(row.avg_value) if row.avg_value is not None else 0.0,
                "host_id": host_id,
            }
            for row in result
        ]
    except Exception as exc:
        logger.warning(
            "Falha ao consultar TimescaleDB metrics, usando lista vazia: %s", exc
        )
        return []
    finally:
        try:
            await session.rollback()
        except Exception:
            pass
        await session.close()


def _fetch_related_logs(
    host_id: str,
    trigger_id: str,
) -> list[str]:
    """Busca logs sanitizados relacionados ao trigger."""
    logger.debug("Buscando logs | host_id=%s trigger_id=%s", host_id, trigger_id)
    raw_logs = [
        f"[{host_id}] Trigger {trigger_id} fired: threshold exceeded",
        f"[{host_id}] Service check failed: connection refused",
    ]
    return [sanitize(log) for log in raw_logs]


async def _async_fetch_similar_incidents(
    title: str,
    description: str,
    fingerprint: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Busca incidentes similares via pgvector (cosine similarity) baseado no novo incidente."""
    # Gera embedding do título e descrição do incidente atual
    text_to_embed = f"{title}\n{description}"
    embedding = generate_embedding(text_to_embed)
    if not embedding or all(v == 0.0 for v in embedding):
        return []

    session = SessionLocal()
    try:
        # pgvector cosine distance operator é <=>
        similar_query = text("""
            SELECT incident_fingerprint, summary, root_cause,
                   1 - (embedding <=> :embedding) AS similarity
            FROM n_infraops_incident_reports
            WHERE incident_fingerprint != :fingerprint AND embedding IS NOT NULL
            ORDER BY embedding <=> :embedding
            LIMIT :limit
        """)
        similar_result = await session.execute(
            similar_query,
            {"embedding": embedding, "fingerprint": fingerprint, "limit": limit},
        )
        return [
            {
                "fingerprint": r.incident_fingerprint,
                "summary": r.summary,
                "root_cause": r.root_cause,
                "similarity": float(r.similarity) if r.similarity is not None else 0.0,
            }
            for r in similar_result
        ]
    except Exception as exc:
        logger.warning("Falha ao buscar incidentes similares via pgvector: %s", exc)
        return []
    finally:
        try:
            await session.rollback()
        except Exception:
            pass
        await session.close()


async def _async_save_report(report_data: dict[str, Any]) -> None:
    """Persiste relatório na tabela `n_infraops_incident_reports` utilizando SQLAlchemy."""
    session = SessionLocal()
    try:
        db_report = IncidentReport(
            incident_fingerprint=report_data.get("incident_fingerprint"),
            deskmanager_ticket_id=report_data.get("deskmanager_ticket_id"),
            markdown_report=report_data.get("markdown_report", ""),
            summary=report_data.get("summary", ""),
            root_cause=report_data.get("root_cause", ""),
            blast_radius=report_data.get("blast_radius", []),
            corrective_actions=report_data.get("corrective_actions", []),
            timeline=report_data.get("timeline", []),
            embedding=report_data.get("embedding"),
            gemini_model_used=report_data.get("gemini_model_used"),
            prompt_tokens=report_data.get("prompt_tokens", 0),
            completion_tokens=report_data.get("completion_tokens", 0),
        )
        session.add(db_report)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.error("Falha ao persistir relatório: %s", exc)
        raise exc
    finally:
        try:
            await session.rollback()
        except Exception:
            pass
        await session.close()
