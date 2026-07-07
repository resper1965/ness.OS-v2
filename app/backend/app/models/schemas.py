# -------------------------------------------------------
# NessOps — Modelos Pydantic (contratos da API e domínio)
# -------------------------------------------------------
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- Severidades Zabbix ---
class ZabbixSeverity(int, enum.Enum):
    NOT_CLASSIFIED = 0
    INFORMATION = 1
    WARNING = 2
    AVERAGE = 3
    HIGH = 4
    DISASTER = 5


# --- Payload do webhook Zabbix ---
class ZabbixAlertPayload(BaseModel):
    """Payload que o Zabbix envia via webhook media type."""

    event_id: str = Field(..., description="ID do evento no Zabbix")
    host_id: str = Field(..., description="ID do host")
    host_name: str = Field(..., description="Nome do host")
    host_ip: str = Field(default="", description="IP do host")
    trigger_id: str = Field(..., description="ID do trigger")
    trigger_name: str = Field(..., description="Nome do trigger")
    trigger_description: str = Field(default="", description="Descrição do trigger")
    severity: ZabbixSeverity = Field(default=ZabbixSeverity.AVERAGE)
    status: str = Field(default="PROBLEM", description="PROBLEM ou RESOLVED")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tags: dict[str, str] = Field(default_factory=dict)
    items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Valores dos items relacionados ao trigger",
    )


# --- Resposta do webhook ---
class AlertResponse(BaseModel):
    fingerprint: str
    accepted: bool = True
    queue: str = Field(
        default="primary",
        description="primary = lock adquirido, deferred = aguardando",
    )


# --- Incidente (domínio interno) ---
class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Incident(BaseModel):
    """Incidente correlacionado (agrupa 1..N alertas)."""

    fingerprint: str
    title: str
    severity: ZabbixSeverity
    status: IncidentStatus = IncidentStatus.OPEN
    host_id: str
    host_name: str
    trigger_id: str
    alert_count: int = 1
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    sanitized_description: str = ""
    tags: dict[str, str] = Field(default_factory=dict)


# --- Resultado de anomalia ---
class AnomalyResult(BaseModel):
    item_id: str
    host_id: str
    current_value: float
    z_score: float
    median: float
    mad: float
    is_anomaly: bool
    threshold: float


# --- Payload para n8n (dispara DeskManager + WhatsApp) ---
class N8nIncidentPayload(BaseModel):
    """Payload enviado ao webhook do n8n quando um incidente é consolidado.

    O n8n usa este payload para:
      1. Abrir ticket no DeskManager via API Rest.
      2. Enviar alerta read-only no WhatsApp via Evolution API.
    """

    fingerprint: str
    title: str
    severity: ZabbixSeverity
    severity_label: str = Field(
        default="AVERAGE",
        description="Label legível da severidade (DISASTER, HIGH, etc.)",
    )
    status: IncidentStatus = IncidentStatus.OPEN
    host_id: str
    host_name: str
    trigger_id: str
    trigger_name: str
    sanitized_description: str
    alert_count: int = 1
    first_seen: str = Field(description="ISO 8601 timestamp")
    last_seen: str = Field(description="ISO 8601 timestamp")
    tags: dict[str, str] = Field(default_factory=dict)

    # Links prontos para o template do WhatsApp
    dashboard_url: str = Field(
        default="",
        description="URL direta do incidente no dashboard n.infraops",
    )
    deskmanager_ticket_id: str | None = Field(
        default=None,
        description="ID do ticket retornado pelo DeskManager (preenchido pelo n8n)",
    )

    # Achados técnicos mastigados para o NOC
    findings_summary: str = Field(
        default="",
        description="Resumo técnico curto para o template WhatsApp",
    )


# --- Post-Mortem Report ---
class PostMortemReport(BaseModel):
    """Relatório pós-incidente gerado pelo Gemini.

    Persistido em `incident_reports` e inserido no DeskManager
    como Interação Interna.
    """

    incident_fingerprint: str
    deskmanager_ticket_id: str | None = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # Conteúdo Markdown gerado pelo Gemini
    markdown_report: str = Field(
        description="Relatório completo em Markdown",
    )

    # Metadados do relatório
    summary: str = Field(description="Resumo executivo (1-2 frases)")
    root_cause: str = Field(description="Causa raiz provável")
    blast_radius: list[str] = Field(
        default_factory=list,
        description="Lista de serviços/hosts afetados",
    )
    corrective_actions: list[str] = Field(
        default_factory=list,
        description="Ações corretivas recomendadas",
    )
    timeline: list[dict[str, str]] = Field(
        default_factory=list,
        description="Linha do tempo [{timestamp, event}]",
    )

    # Controle
    gemini_model_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


# --- WhatsApp Notification (Read-Only) ---
class WhatsAppAlertMessage(BaseModel):
    """Template de mensagem para o Evolution API.

    Estritamente read-only: sem botões interativos,
    sem chatbot, sem resposta. Apenas texto + links.
    """

    group_id: str = Field(description="ID do grupo WhatsApp do NOC")
    message: str = Field(description="Mensagem formatada pronta para envio")


# --- Payload de Entrada do Keep (RCA) ---
class IncidentAnalyzeRequest(BaseModel):
    """Payload recebido do Keep AIOps para gerar PostMortem."""
    
    incident_data: dict[str, Any] = Field(
        description="Dados sanitizados do incidente, agrupados pelo Keep"
    )
    ticket_id: str | None = Field(
        default=None,
        description="ID do ticket no DeskManager (se já criado pelo n8n)"
    )


