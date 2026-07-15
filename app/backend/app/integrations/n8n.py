# -------------------------------------------------------
# n.infraops — Cliente n8n (dispara workflows de borda)
# -------------------------------------------------------
"""
Envia payloads para webhooks do n8n que orquestram:
  1. Abertura de ticket no DeskManager.
  2. Alerta read-only no WhatsApp via Evolution API.
  3. Inserção de post-mortem no DeskManager como Interação Interna.

O n8n é o "edge orchestrator" — o backend Python NÃO chama
DeskManager ou Evolution diretamente. Isso isola a lógica de
integração no n8n (visual, editável, sem deploy).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings
from app.models.schemas import (
    N8nIncidentPayload,
    PostMortemReport,
    ZabbixSeverity,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Timeout agressivo: n8n é local, não pode bloquear o worker
_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)


def _severity_label(severity: ZabbixSeverity) -> str:
    """Converte enum numérico para label legível."""
    return {
        ZabbixSeverity.NOT_CLASSIFIED: "INFO",
        ZabbixSeverity.INFORMATION: "INFO",
        ZabbixSeverity.WARNING: "WARNING",
        ZabbixSeverity.AVERAGE: "AVERAGE",
        ZabbixSeverity.HIGH: "HIGH",
        ZabbixSeverity.DISASTER: "DISASTER",
    }.get(severity, "UNKNOWN")


def _severity_emoji(severity: ZabbixSeverity) -> str:
    """Emoji para mensagem do WhatsApp."""
    return {
        ZabbixSeverity.NOT_CLASSIFIED: "ℹ️",
        ZabbixSeverity.INFORMATION: "ℹ️",
        ZabbixSeverity.WARNING: "⚠️",
        ZabbixSeverity.AVERAGE: "🟠",
        ZabbixSeverity.HIGH: "🔴",
        ZabbixSeverity.DISASTER: "🚨",
    }.get(severity, "❓")


def build_incident_payload(
    incident: dict[str, Any],
) -> N8nIncidentPayload:
    """Monta payload tipado para o webhook do n8n.

    Chamado após upsert do incidente no PostgreSQL.
    """
    severity = ZabbixSeverity(incident.get("severity", 3))
    fingerprint = incident["fingerprint"]

    # Resumo técnico mastigado para o NOC
    findings = (
        f"Host: {incident.get('host_name', '?')}\n"
        f"Trigger: {incident.get('title', '?')}\n"
        f"Severidade: {_severity_label(severity)}\n"
        f"Alertas agrupados: {incident.get('alert_count', 1)}\n"
        f"Descrição: {incident.get('sanitized_description', 'N/A')}"
    )

    return N8nIncidentPayload(
        fingerprint=fingerprint,
        title=incident.get("title", "Incidente sem título"),
        severity=severity,
        severity_label=_severity_label(severity),
        host_id=incident.get("host_id", ""),
        host_name=incident.get("host_name", ""),
        trigger_id=incident.get("trigger_id", ""),
        trigger_name=incident.get("title", ""),
        sanitized_description=incident.get("sanitized_description", ""),
        alert_count=incident.get("alert_count", 1),
        first_seen=incident.get("first_seen", ""),
        last_seen=incident.get("last_seen", ""),
        tags=incident.get("tags", {}),
        dashboard_url=f"{settings.dashboard_base_url}/incidents/{fingerprint}",
        findings_summary=findings,
    )


def build_whatsapp_message(payload: N8nIncidentPayload) -> str:
    """Formata mensagem de texto para WhatsApp (read-only, sem botões).

    Texto descritivo com links diretos para ticket e dashboard.
    """
    emoji = _severity_emoji(payload.severity)
    ticket_line = ""
    if payload.deskmanager_ticket_id:
        ticket_line = (
            f"🎫 Ticket: {settings.deskmanager_api_url}"
            f"/tickets/{payload.deskmanager_ticket_id}\n"
        )

    return (
        f"{emoji} *n.infraops — Incidente Detectado*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Host:* {payload.host_name}\n"
        f"*Trigger:* {payload.trigger_name}\n"
        f"*Severidade:* {payload.severity_label}\n"
        f"*Alertas agrupados:* {payload.alert_count}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{payload.sanitized_description}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ticket_line}"
        f"📊 Dashboard: {payload.dashboard_url}\n"
        f"⏰ Desde: {payload.first_seen}"
    )


def notify_incident_created(incident: dict[str, Any]) -> dict[str, Any]:
    """Dispara webhook do n8n para novo incidente (síncrono).

    O n8n então:
      1. Chama API DeskManager → cria ticket → captura ticket_id.
      2. Chama Evolution API → envia WhatsApp com ticket_id e links.

    Retorna a resposta do n8n (contendo ticket_id do DeskManager).
    """
    payload = build_incident_payload(incident)
    url = f"{settings.n8n_base_url}{settings.n8n_webhook_incident}"

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(url, json=payload.model_dump(mode="json"))
            response.raise_for_status()
            result = response.json()

        logger.info(
            "n8n notificado | fingerprint=%s ticket_id=%s",
            payload.fingerprint,
            result.get("ticket_id"),
        )
        return result

    except httpx.HTTPError as exc:
        logger.error("Falha ao notificar n8n: %s", exc)
        # Não re-raise: notificação é best-effort, não bloqueia pipeline
        return {"error": str(exc), "ticket_id": None}


def notify_postmortem_ready(
    report: PostMortemReport,
) -> dict[str, Any]:
    """Dispara webhook do n8n para post-mortem gerado.

    O n8n então:
      1. Insere o Markdown como Interação Interna no DeskManager.
      2. (Opcional) Notifica no Slack com link do relatório.
    """
    url = f"{settings.n8n_base_url}{settings.n8n_webhook_postmortem}"

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(url, json=report.model_dump(mode="json"))
            response.raise_for_status()
            return response.json()

    except httpx.HTTPError as exc:
        logger.error("Falha ao enviar post-mortem ao n8n: %s", exc)
        return {"error": str(exc)}


def notify_soc_triage_decision(decision_data: dict[str, Any]) -> dict[str, Any]:
    """Dispara webhook do n8n para nova decisão de triagem do SOC.

    O n8n então:
      1. Abre chamado de segurança no GLPI (ou DeskManager).
      2. Envia alerta no WhatsApp se a severidade for HIGH ou CRIT.
    """
    url = f"{settings.n8n_base_url}{settings.n8n_webhook_soc}"

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(url, json=decision_data)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        logger.error("Falha ao enviar decisão de triagem SOC ao n8n: %s", exc)
        return {"error": str(exc)}

