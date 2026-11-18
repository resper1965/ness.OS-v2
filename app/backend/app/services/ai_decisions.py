"""Registro de cada chamada de IA em n_ai_decisions (idempotente por kind+source_ref)."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_context import AICall
from app.models.models import AIDecision

logger = logging.getLogger(__name__)


def _cost(value) -> Decimal | None:
    """Cabe em NUMERIC(10,6) ou vira None; custo estranho do provedor não derruba o insert."""
    if isinstance(value, bool):
        return None
    try:
        cost = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return cost if cost.is_finite() and 0 <= cost < 10000 else None


async def record_ai_decision(
    session: AsyncSession,
    *,
    kind: str,
    customer_id: str,
    source_ref: str,
    call: AICall,
    prompt_version: str,
    request: dict,
    response: dict,
    rule_value: str | None,
    model_value: str | None,
    incident_id: int | None = None,
    soc_decision_id: int | None = None,
    ticket_id: str | None = None,
    divergent: bool | None = None,
) -> int | None:
    """Id da linha nova, ou None no replay ou em falha (logada; o chamador segue).

    Replay (retry do Celery) soma custo e tokens e completa ticket/incidente.
    `divergent`, quando informado, prevalece sobre rule_value != model_value
    (vocabulários diferentes, ex.: SOC).
    """
    insert = pg_insert(AIDecision).values(
        kind=kind,
        customer_id=customer_id,
        incident_id=incident_id,
        soc_decision_id=soc_decision_id,
        ticket_id=ticket_id,
        source_ref=source_ref,
        outcome=call.outcome,
        model=call.model,
        prompt_version=prompt_version,
        request=request,
        response=response,
        rule_value=rule_value,
        model_value=model_value,
        divergent=(
            divergent
            if divergent is not None
            else rule_value is not None
            and model_value is not None
            and rule_value != model_value
        ),
        latency_ms=call.latency_ms,
        prompt_tokens=call.prompt_tokens,
        completion_tokens=call.completion_tokens,
        cost_usd=_cost(call.cost_usd),
    )
    old, new = AIDecision.__table__.c, insert.excluded
    stmt: Any = insert.on_conflict_do_update(
        index_elements=["kind", "source_ref"],
        set_={
            # a+b, or whichever is set, NULL only when both are NULL
            k: func.coalesce(old[k] + new[k], old[k], new[k])
            for k in ("cost_usd", "prompt_tokens", "completion_tokens")
        }
        | {
            "ticket_id": func.coalesce(new.ticket_id, old.ticket_id),
            "incident_id": func.coalesce(old.incident_id, new.incident_id),
        },
    ).returning(AIDecision.id, literal_column("xmax = 0"))
    try:
        async with session.begin_nested():
            row_id, inserted = (await session.execute(stmt)).one()
            return row_id if inserted else None
    except Exception:  # noqa: BLE001 — registro nunca derruba o chamado
        logger.exception("ai decision not recorded: %s %s", kind, source_ref)
        return None
