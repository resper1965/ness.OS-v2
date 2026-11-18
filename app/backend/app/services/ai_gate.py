"""Portas antes de qualquer chamada ao modelo: cliente desligado e teto mensal global."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.email import ResendEmailClient
from app.models.models import AIDecision
from app.services.customers import resolve_customer
from app.services.policy_params import platform_params

logger = logging.getLogger("nessops.ai_gate")


async def ai_gate(session: AsyncSession, customer_name: str) -> str | None:
    """None = a IA pode rodar; senão o outcome a registrar (cliente antes do teto)."""
    customer = await resolve_customer(session, customer_name)
    if customer is not None and not customer.ai_external_allowed:
        return "skipped_customer"

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    in_month = AIDecision.created_at >= month_start
    # ponytail: full scan of n_ai_decisions per alert; upgrade path: index on created_at (or monthly rollup) when volume demands.
    spent = await session.scalar(
        select(func.coalesce(func.sum(AIDecision.cost_usd), 0)).where(in_month)
    )
    limit_cents = (await platform_params(session))["ai_monthly_budget_cents"]
    if Decimal(spent or 0) * 100 < limit_cents:
        return None

    already_alerted = await session.scalar(
        select(AIDecision.id)
        .where(in_month, AIDecision.outcome == "skipped_budget")
        .limit(1)
    )
    if already_alerted is None:
        await _alert(f"{now:%Y-%m}", Decimal(spent or 0), limit_cents)
    return "skipped_budget"


async def _alert(month: str, spent: Decimal, limit_cents: int) -> None:
    settings = get_settings()
    if not (settings.ai_budget_alert_email and settings.transactional_email_enabled):
        logger.warning("ai budget reached for %s; alert email not configured", month)
        return
    try:
        await ResendEmailClient.from_settings(settings).send(
            to=[settings.ai_budget_alert_email],
            subject=f"ness.OS: teto mensal de IA atingido ({month})",
            idempotency_key=f"ai-budget-{month}",
            text=(
                f"Gasto de IA em {month}: US$ {spent:.2f} "
                f"(teto US$ {limit_cents / 100:.2f}). "
                "Novas análises ficam suspensas até o próximo mês ou ajuste do teto."
            ),
        )
    except Exception:  # noqa: BLE001 — alerta nunca derruba o chamador
        logger.exception("ai budget alert email failed for %s", month)
