# -------------------------------------------------------
# n.infraops — Modelo de Usuários (FASE 4.1)
# -------------------------------------------------------
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserRole(str, enum.Enum):
    """Roles disponíveis na plataforma ness.OS.

    O papel vem sempre do banco (ADR 0015); claims do IdP não o definem.
    """

    platform_admin = "platform_admin"
    admin = "admin"
    operator = "operator"
    viewer = "viewer"
    noc = "noc"
    soc = "soc"
    helpdesk = "helpdesk"
    gestao = "gestao"
    cliente = "cliente"


class User(Base):
    """Tabela de usuários da plataforma n.infraops."""

    __tablename__ = "n_infraops_users"
    __table_args__ = (
        # O login do GLPI é a parte local do e-mail; precisa ser único de forma atômica.
        Index(
            "uq_users_glpi_login",
            func.lower(func.split_part(text("email"), "@", 1)),
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole", create_type=True),
        nullable=False,
        default=UserRole.noc,
        server_default="noc",
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    session_epoch: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_oncall: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dnd_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # do-not-disturb (horas de silêncio)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r} role={self.role}>"


class ClientSummary(Base):
    """Resumo diário/semanal entregue ao gestor de um cliente (idempotente por chave)."""

    __tablename__ = "n_infraops_client_summaries"
    __table_args__ = (
        UniqueConstraint("customer_id", "key", name="uq_client_summaries_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("n_infraops_customers.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # ex.: "2026-11-27-daily"
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # "daily" ou "weekly"
    html: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
