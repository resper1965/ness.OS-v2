# -------------------------------------------------------
# NessOps — Modelos Pydantic (contratos da API e domínio)
# -------------------------------------------------------
from __future__ import annotations

import enum
from datetime import UTC, datetime
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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
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
    first_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
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


# --- Post-Mortem Report ---
class PostMortemReport(BaseModel):
    """Relatório pós-incidente gerado pelo Gemini.

    Persistido em `incident_reports` e inserido no DeskManager
    como Interação Interna.
    """

    incident_fingerprint: str
    deskmanager_ticket_id: str | None = None
    host_name: str | None = None
    customer_name: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

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
    embedding: list[float] | None = None
    gemini_model_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


# --- Solicitação de análise de incidente (RCA) ---
class IncidentAnalyzeRequest(BaseModel):
    """Payload recebido pela API para gerar PostMortem."""

    incident_data: dict[str, Any] = Field(
        description="Dados sanitizados do incidente consolidado"
    )
    ticket_id: str | None = Field(
        default=None, description="ID do ticket no DeskManager (se já criado)"
    )


class GlpiWebhookPayload(BaseModel):
    """Payload recebido do webhook do GLPI ao resolver um ticket."""

    ticket_id: str = Field(..., description="ID do ticket no GLPI")
    status: str = Field(
        ..., description="Status do ticket no GLPI (ex: solved, closed)"
    )
    solution: str = Field(
        default="", description="Texto de solução preenchido pelo técnico"
    )


# --- PWA Push Notifications ---
class PushKeysSchema(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeRequest(BaseModel):
    endpoint: str
    keys: PushKeysSchema


class PushUnsubscribeRequest(BaseModel):
    endpoint: str
