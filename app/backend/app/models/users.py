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
    Integer,
    String,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserRole(str, enum.Enum):
    """Roles disponíveis na plataforma ness.OS.

    Mapeamento Authentik SSO → UserRole:
      platform_admin → platform_admin
      admin    → admin
      noc      → noc
      soc      → soc
      helpdesk → helpdesk
      gestao   → gestao
      usuarios → cliente
    """

    platform_admin = "platform_admin"
    admin = "admin"
    noc = "noc"
    soc = "soc"
    helpdesk = "helpdesk"
    gestao = "gestao"
    cliente = "cliente"


class User(Base):
    """Tabela de usuários da plataforma n.infraops."""

    __tablename__ = "n_infraops_users"

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
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
