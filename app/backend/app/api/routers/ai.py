"""Retorno do analista sobre decisões de IA, listagem recente e métricas (NOC/SOC)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import TIMESTAMP, Float, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_noc, resolve_tenant_scope
from app.database import get_db
from app.models.models import AIDecision, Incident
from app.models.users import User
from app.services.policy_params import platform_params

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Outcomes that should carry a cost (error = no response, skipped_* = never called).
CALLED = ("ok",)


class FeedbackIn(BaseModel):
    verdict: Literal["useful", "wrong", "unread"]


def _scope_filter(scope: str | None) -> list:
    return [func.lower(AIDecision.customer_id) == scope.lower()] if scope else []


@router.post("/decisions/{decision_id}/feedback")
async def set_feedback(
    decision_id: int,
    body: FeedbackIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_noc),
) -> dict[str, Any]:
    scope = resolve_tenant_scope(user, None)
    decision = await db.get(AIDecision, decision_id)
    if decision is None or (scope and decision.customer_id.lower() != scope.lower()):
        raise HTTPException(status_code=404, detail="Decisão não encontrada")
    decision.feedback = body.verdict
    decision.feedback_user_id = user.id
    decision.feedback_at = datetime.now(UTC)
    await db.commit()
    return {
        "id": decision.id,
        "feedback": decision.feedback,
        "feedback_at": decision.feedback_at.isoformat(),
    }


@router.get("/decisions")
async def list_decisions(
    kind: str | None = Query(None),
    customer_id: str | None = Query(None),
    divergent: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_noc),
) -> list[dict[str, Any]]:
    where = _scope_filter(resolve_tenant_scope(user, customer_id))
    if kind:
        where.append(AIDecision.kind == kind)
    if divergent is not None:
        where.append(AIDecision.divergent.is_(divergent))
    rows = (
        (
            await db.execute(
                select(AIDecision)
                .where(*where)
                .order_by(AIDecision.created_at.desc(), AIDecision.id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": d.id,
            "kind": d.kind,
            "customer_id": d.customer_id,
            "ticket_id": d.ticket_id,
            "outcome": d.outcome,
            "model": d.model,
            "rule_value": d.rule_value,
            "model_value": d.model_value,
            "divergent": d.divergent,
            "feedback": d.feedback,
            "cost_usd": None if d.cost_usd is None else float(d.cost_usd),
            "created_at": d.created_at.isoformat(),
        }
        for d in rows
    ]


def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


@router.get("/metrics")
async def metrics(
    days: int = Query(30, ge=1, le=365),
    customer_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_noc),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    where = [
        AIDecision.created_at >= now - timedelta(days=days),
        *_scope_filter(resolve_tenant_scope(user, customer_id)),
    ]
    d = AIDecision
    # Resolution time comes from the linked incident; no incident or tag = no MTTR sample.
    # Malformed tags and negative durations (resolved before created) are no sample.
    raw = Incident.tags["glpi_resolved_at"].astext
    resolved_at = case(
        (raw.op("~")(r"^\d{4}-\d{2}-\d{2}T"), cast(raw, TIMESTAMP(timezone=True)))
    )
    minutes = case(
        (
            resolved_at >= d.created_at,
            func.extract("epoch", resolved_at - d.created_at).cast(Float) / 60,
        )
    )
    useful = d.feedback == "useful"
    kinds = (
        await db.execute(
            select(
                d.kind,
                func.count(),
                func.count().filter(d.divergent),
                func.count().filter(useful),
                func.count().filter(d.feedback == "wrong"),
                func.count().filter(d.feedback == "unread"),
                func.count().filter(d.feedback.is_(None)),
                func.coalesce(func.sum(d.cost_usd), 0),
                func.count().filter(d.cost_usd.is_(None), d.outcome.in_(CALLED)),
                func.avg(d.latency_ms),
                func.avg(minutes).filter(useful),
                func.avg(minutes).filter(d.feedback.is_distinct_from("useful")),
            )
            .select_from(d)
            .outerjoin(Incident, Incident.id == d.incident_id)
            .where(*where)
            .group_by(d.kind)
            .order_by(d.kind)
        )
    ).all()
    outcomes: dict[str, dict[str, int]] = {}
    for kind, outcome, n in await db.execute(
        select(d.kind, d.outcome, func.count())
        .where(*where)
        .group_by(d.kind, d.outcome)
    ):
        outcomes.setdefault(kind, {})[outcome] = n

    by_kind: dict[str, Any] = {}
    for kind, total, div, fu, fw, fn, fnone, cost, missing, lat, m_u, m_o in kinds:
        by_kind[kind] = {
            "total": total,
            "by_outcome": outcomes.get(kind, {}),
            "divergence_rate": div / total,
            "feedback": {"useful": fu, "wrong": fw, "unread": fn, "none": fnone},
            "useful_rate": _rate(fu, fu + fw + fn),
            "cost_usd": float(cost),
            "cost_missing": missing,
            "avg_latency_ms": None if lat is None else float(lat),
            "failure_rate": outcomes.get(kind, {}).get("error", 0) / total,
            "mttr_minutes": {
                "useful": None if m_u is None else float(m_u),
                "other": None if m_o is None else float(m_o),
            },
        }

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = await db.scalar(
        select(func.coalesce(func.sum(d.cost_usd), 0)).where(
            d.created_at >= month_start
        )
    )
    cents = (await platform_params(db))["ai_monthly_budget_cents"]
    return {
        "window_days": days,
        "budget": {"month_cost_usd": float(spent or 0), "limit_usd": cents / 100},
        "by_kind": by_kind,
    }
