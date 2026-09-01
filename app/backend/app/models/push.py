# -------------------------------------------------------
# n.infraops — Modelo de Subscrições do Web Push (PWA)
# -------------------------------------------------------
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PushSubscription(Base):
    """Armazena as subscrições de navegadores para recebimento de Web Push."""

    __tablename__ = "n_infraops_push_subscriptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("n_infraops_users.id", ondelete="CASCADE"),
        nullable=True,
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    auth_key: Mapped[str] = mapped_column(String(255), nullable=False)
    p256dh_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relacionamento opcional com User
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<PushSubscription id={self.id} tenant_id={self.tenant_id!r} endpoint={self.endpoint[:30]}...>"
