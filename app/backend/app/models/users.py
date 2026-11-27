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


class Identity(Base):
    """Vínculo (issuer, subject) do IdP -> User local (ADR 0015). Nunca por e-mail."""

    __tablename__ = "n_infraops_identities"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_identities_iss_sub"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("n_infraops_users.id"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("n_infraops_users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PendingLogin(Base):
    """Identidade do IdP recusada por falta de vínculo; o admin escolhe a pessoa e vincula."""

    __tablename__ = "n_infraops_pending_logins"

    issuer: Mapped[str] = mapped_column(String(512), primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
