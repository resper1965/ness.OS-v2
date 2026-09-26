# -------------------------------------------------------
# n.infraops — Modelos de Banco de Dados (SQLAlchemy Async)
# -------------------------------------------------------
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AssetType(str, enum.Enum):
    UNKNOWN = "unknown"
    WINDOWS = "windows"
    LINUX = "linux"
    NETWORK_DEVICE = "network_device"


class RmmProvider(str, enum.Enum):
    DATTO = "datto"
    ATERA = "atera"
    NONE = "none"


class AssetStatus(str, enum.Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"


class Asset(Base):
    """Representação de ativos monitorados e gerenciados."""

    __tablename__ = "n_infraops_assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Identidade Zabbix (source of truth)
    zabbix_host_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET)
    fqdn: Mapped[str | None] = mapped_column(String(512))

    # Classificação
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(
            AssetType,
            name="asset_type",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AssetType.LINUX,
    )
    status: Mapped[AssetStatus] = mapped_column(
        Enum(
            AssetStatus,
            name="asset_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AssetStatus.ACTIVE,
    )

    # Multi-RMM
    rmm_provider: Mapped[RmmProvider] = mapped_column(
        Enum(
            RmmProvider,
            name="rmm_provider",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=RmmProvider.NONE,
    )
    rmm_device_id: Mapped[str | None] = mapped_column(String(128))
    rmm_site_id: Mapped[str | None] = mapped_column(String(128))

    # Metadados
    os_family: Mapped[str | None] = mapped_column(String(64))
    os_version: Mapped[str | None] = mapped_column(String(64))
    customer_id: Mapped[str | None] = mapped_column(String(128), index=True)
    customer_name: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    # Credenciais SSH
    ssh_port: Mapped[int | None] = mapped_column(
        Integer, default=22, server_default="22"
    )
    ssh_username: Mapped[str | None] = mapped_column(String(64))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relacionamentos
    incidents: Mapped[list[Incident]] = relationship("Incident", back_populates="asset")
    playbook_executions: Mapped[list[PlaybookExecution]] = relationship(
        "PlaybookExecution", back_populates="asset"
    )


class Incident(Base):
    """Incidentes agregados e correlacionados de alertas Zabbix."""

    __tablename__ = "n_infraops_incidents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    severity: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=3, server_default="3"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="open", server_default="open"
    )

    # Zabbix IDs
    host_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    host_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Link ao ativo (opcional, resolvido pelo processador)
    asset_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("n_infraops_assets.id")
    )

    # Contagem e timestamps
    alert_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Descrição e tags
    sanitized_description: Mapped[str | None] = mapped_column(Text, default="")
    tags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    # Ticket externo
    deskmanager_ticket_id: Mapped[str | None] = mapped_column(String(64))

    # Timestamps controle
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relacionamentos
    asset: Mapped[Asset | None] = relationship("Asset", back_populates="incidents")
    reports: Mapped[list[IncidentReport]] = relationship(
        "IncidentReport", back_populates="incident"
    )
    playbook_executions: Mapped[list[PlaybookExecution]] = relationship(
        "PlaybookExecution", back_populates="incident"
    )


class IncidentReport(Base):
    """Relatórios pós-incidente gerados pela IA (RAG / Gemini)."""

    __tablename__ = "n_infraops_incident_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_fingerprint: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("n_infraops_incidents.fingerprint"),
        nullable=False,
        index=True,
    )
    deskmanager_ticket_id: Mapped[str | None] = mapped_column(String(64))

    # Conteúdo IA
    markdown_report: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    blast_radius: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    corrective_actions: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    timeline: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )

    # Embedding para RAG semântico (768 dimensões para Gemini)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))

    # Metadados
    gemini_model_used: Mapped[str | None] = mapped_column(String(64))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    # Timestamps
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relacionamentos
    incident: Mapped[Incident] = relationship("Incident", back_populates="reports")


class PlaybookExecution(Base):
    """Registro de auditoria para execuções de remediação."""

    __tablename__ = "n_infraops_playbook_executions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("n_infraops_incidents.id"), index=True
    )
    asset_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("n_infraops_assets.id"), index=True
    )

    # Definição e provedor
    playbook_name: Mapped[str] = mapped_column(String(128), nullable=False)
    rmm_provider: Mapped[RmmProvider] = mapped_column(
        Enum(
            RmmProvider,
            name="rmm_provider",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    execution_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="manual", server_default="manual"
    )

    # Status e aprovação
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    output: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # Relacionamentos
    incident: Mapped[Incident | None] = relationship(
        "Incident", back_populates="playbook_executions"
    )
    asset: Mapped[Asset | None] = relationship(
        "Asset", back_populates="playbook_executions"
    )


class Metric(Base):
    """Métricas de séries temporais do host."""

    __tablename__ = "n_infraops_metrics"

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    host_id: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)
    item_id: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)
    item_key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[float] = mapped_column(nullable=False)


class CustomerCredentials(Base):
    """Credenciais de RMM de cada cliente (multi-tenant)."""

    __tablename__ = "n_infraops_customer_credentials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # 'datto', 'atera'
    api_key: Mapped[str] = mapped_column(String(255), nullable=False)
    api_secret: Mapped[str | None] = mapped_column(String(255))
    api_url: Mapped[str | None] = mapped_column(String(512))

    # ID deste cliente dentro do RMM (ex: CustomerID no Atera)
    rmm_customer_id: Mapped[str | None] = mapped_column(String(128), index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TenantMapping(Base):
    """Mapeamento explícito de IDs de plataformas externas para Clientes internos."""

    __tablename__ = "n_infraops_tenant_mappings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    internal_customer_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )

    external_platform: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # 'atera', 'datto', 'zabbix'
    external_customer_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    external_customer_name: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SocDecision(Base):
    """Registro de decisões de triagem e inteligência geradas pelo Analista SOC IA."""

    __tablename__ = "n_secops_soc_decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wazuh_rule_id: Mapped[str] = mapped_column(String(64), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), index=True)
    agent_name: Mapped[str | None] = mapped_column(String(255))
    customer_id: Mapped[str | None] = mapped_column(String(128), index=True)

    classification: Mapped[str] = mapped_column(
        String(32), index=True
    )  # FP, LOW, MED, HIGH, CRIT
    confidence: Mapped[float] = mapped_column(nullable=False, default=1.0)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[str] = mapped_column(String(255), nullable=False)

    raw_alert: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
