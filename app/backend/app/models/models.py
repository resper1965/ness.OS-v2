# -------------------------------------------------------
# n.infraops — Modelos de Banco de Dados (SQLAlchemy Async)
# -------------------------------------------------------
from __future__ import annotations

import enum
from datetime import date, datetime, time
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
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
    assigned_user_id: Mapped[int | None] = mapped_column(BigInteger)

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


class IncidentAction(Base):
    """Durable, attributable history of operator and integration actions."""

    __tablename__ = "n_infraops_incident_actions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("n_infraops_incidents.id"), nullable=False
    )
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    actor_source: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str | None] = mapped_column(String(32))
    previous_assignee_id: Mapped[int | None] = mapped_column(BigInteger)
    new_assignee_id: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Notification(Base):
    """Uma tentativa de aviso (incidente x destinatário x canal x degrau).

    `provider_result` é só o aceite do provedor; leitura/reconhecimento é
    `acknowledged_at`; resolução é `resolved_at` (estados distintos).
    """

    __tablename__ = "n_infraops_notifications"
    __table_args__ = (
        UniqueConstraint(
            "incident_id", "user_id", "channel", "step", name="uq_notifications_slot"
        ),
        CheckConstraint(
            "channel IN ('email', 'push')", name="ck_notifications_channel"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("n_infraops_incidents.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("n_infraops_users.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    step: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Lease da tentativa: `claimed_at` + sem resultado de provedor = pendente/abandonada.
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_result: Mapped[str | None] = mapped_column(Text)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ack_type: Mapped[str | None] = mapped_column(String(16))
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    __table_args__ = (
        CheckConstraint(
            "modality IS NULL OR modality IN ('managed', 'onsite', 'shared')",
            name="ck_tenant_mappings_modality",
        ),
    )

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
    # Nulo = pendente_de_modalidade: a cobertura não é declarada (decisão do Ricardo).
    modality: Mapped[str | None] = mapped_column(String(32))
    operator: Mapped[str | None] = mapped_column(String(128))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Customer(Base):
    """Cadastro do cliente: identidade e entidade GLPI (nenhum contato aqui)."""

    __tablename__ = "n_infraops_customers"
    __table_args__ = (
        Index(
            "uq_customers_active_entity",
            "glpi_entity_id",
            unique=True,
            postgresql_where=text("active"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    glpi_entity_id: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Sem FK, como o resto do projeto.
    updated_by_user_id: Mapped[int | None] = mapped_column(BigInteger)


class CustomerAlias(Base):
    """Apelido normalizado (`lower().strip()`); único entre todos os clientes."""

    __tablename__ = "n_infraops_customer_aliases"

    alias_norm: Mapped[str] = mapped_column(Text, primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("n_infraops_customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class SocDecision(Base):
    """Registro de decisões de triagem e inteligência geradas pelo Analista SOC IA."""

    __tablename__ = "n_secops_soc_decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wazuh_rule_id: Mapped[str] = mapped_column(String(64), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), index=True)
    agent_name: Mapped[str | None] = mapped_column(String(255))
    customer_id: Mapped[str | None] = mapped_column(String(128), index=True)
    # Idempotência: hash de tenant + id do alerta (índice único parcial, ver migrate.py)
    dedup_key: Mapped[str | None] = mapped_column(String(64))
    # Frequência: hash de tenant + cluster + agente + regra; contagem recente é consulta a esta coluna
    freq_key: Mapped[str | None] = mapped_column(String(64))
    # Vínculo opcional com Incident (sem FK, como o resto do projeto); nulo até haver produtor.
    # Índice parcial em migrate.py.
    incident_id: Mapped[int | None] = mapped_column(BigInteger)

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


# --- Contratos e políticas de SLA (editáveis; sem valor embutido no código) ---


class SlaCalendar(Base):
    __tablename__ = "n_infraops_sla_calendars"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="America/Sao_Paulo",
        server_default="America/Sao_Paulo",
    )
    is_24x7: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


class SlaCalendarHours(Base):
    __tablename__ = "n_infraops_sla_calendar_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_sla_hours_weekday"),
        CheckConstraint("start_time < end_time", name="ck_sla_hours_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    calendar_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("n_infraops_sla_calendars.id", ondelete="CASCADE"),
        nullable=False,
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)


class SlaHoliday(Base):
    __tablename__ = "n_infraops_sla_holidays"
    __table_args__ = (
        UniqueConstraint(
            "calendar_id", "holiday_date", name="uq_sla_holidays_calendar_date"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    calendar_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("n_infraops_sla_calendars.id", ondelete="CASCADE"),
        nullable=False,
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class Contract(Base):
    """Contrato de um cliente; `is_default` = padrão interno ness., NÃO contratual."""

    __tablename__ = "n_infraops_contracts"
    __mapper_args__ = {"eager_defaults": True}  # updated_at lido sem lazy load
    __table_args__ = (
        CheckConstraint(
            "modality IS NULL OR modality IN ('managed', 'onsite', 'shared')",
            name="ck_contracts_modality",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'suspended', 'ended')",
            name="ck_contracts_status",
        ),
        CheckConstraint(
            "starts_on IS NULL OR ends_on IS NULL OR starts_on <= ends_on",
            name="ck_contracts_dates",
        ),
        CheckConstraint(
            "(is_default AND tenant_id IS NULL AND NOT contractual AND status = 'active')"
            " OR (NOT is_default AND tenant_id IS NOT NULL AND contractual)",
            name="ck_contracts_default",
        ),
        Index(
            "uq_contracts_tenant_active_ci",
            func.lower(text("tenant_id")),
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_contracts_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(128))
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    contractual: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    modality: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft"
    )
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    calendar_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("n_infraops_sla_calendars.id")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(BigInteger)


class SlaPolicy(Base):
    """Política de prazo do contrato.

    ponytail: `tto_minutes`/`ttr_minutes` só são armazenados e editáveis; nada os lê
    ainda. Upgrade path: o SLM do GLPI passa a lê-los do contrato.
    """

    __tablename__ = "n_infraops_sla_policies"
    __mapper_args__ = {"eager_defaults": True}  # updated_at lido sem lazy load
    __table_args__ = (
        UniqueConstraint("contract_id", "key", name="uq_sla_policies_contract_key"),
        CheckConstraint("ack_minutes BETWEEN 1 AND 43200", name="ck_sla_policies_ack"),
        CheckConstraint(
            "tto_minutes IS NULL OR tto_minutes BETWEEN 1 AND 43200",
            name="ck_sla_policies_tto",
        ),
        CheckConstraint(
            "ttr_minutes IS NULL OR ttr_minutes BETWEEN 1 AND 43200",
            name="ck_sla_policies_ttr",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("n_infraops_contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    min_severity: Mapped[int | None] = mapped_column(SmallInteger)
    severity: Mapped[int | None] = mapped_column(SmallInteger)
    has_tenant: Mapped[bool | None] = mapped_column(Boolean)
    ack_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    tto_minutes: Mapped[int | None] = mapped_column(Integer)
    ttr_minutes: Mapped[int | None] = mapped_column(Integer)
    calendar_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("n_infraops_sla_calendars.id")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(BigInteger)


class EscalationStep(Base):
    __tablename__ = "n_infraops_escalation_steps"
    __mapper_args__ = {"eager_defaults": True}  # updated_at lido sem lazy load
    __table_args__ = (
        UniqueConstraint(
            "contract_id", "position", name="uq_escalation_steps_contract_position"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("n_infraops_contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(BigInteger)


class ContractChange(Base):
    """Trilha de mudança de SLA em contrato ativo."""

    __tablename__ = "n_infraops_contract_changes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("n_infraops_contracts.id"), nullable=False
    )
    changed_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    entity: Mapped[str] = mapped_column(String(32), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
