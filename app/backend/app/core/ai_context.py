"""Allowlisted provider context and authoritative post-incident identity."""

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.sanitizer import sanitize_dict, sanitize_value
from app.database import SessionLocal
from app.models import Incident

logger = logging.getLogger(__name__)

INCIDENT_FIELDS = {
    "title",
    "host_name",
    "trigger_name",
    "trigger_description",
    "sanitized_description",
    "severity",
    "status",
    "timestamp",
    "first_seen",
    "last_seen",
}


def incident_prompt_data(incident):
    return sanitize_dict(
        {key: value for key, value in incident.items() if key in INCIDENT_FIELDS}
    )


class AIRequestV1(BaseModel):
    """Only shape allowed to reach an LLM provider; values are sanitized on build."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    tenant: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    severity: str
    observed_at: datetime  # freshness: when the source event happened
    evidence: dict[str, Any]

    @field_validator("*")
    @classmethod
    def _sanitize(cls, value: Any) -> Any:
        return sanitize_value(value)


def _observed_at(value: Any) -> datetime:
    try:
        return TypeAdapter(datetime).validate_python(value)
    except ValueError:
        # ponytail: unparseable -> now; add strict reject if sources drift
        logger.warning("AI request observed_at unparseable; using current time")
        return datetime.now(UTC)


def incident_ai_request(incident, tenant) -> AIRequestV1:
    severity = incident.get("severity")
    return AIRequestV1(
        tenant=str(tenant or "unknown"),
        source_event_id=str(
            incident.get("event_id") or incident.get("fingerprint") or "unknown"
        ),
        severity=str(getattr(severity, "value", severity)),
        observed_at=_observed_at(
            incident.get("timestamp") or incident.get("last_seen")
        ),
        evidence=incident_prompt_data(incident),
    )


def log_ai_call(kind, outcome, started, usage=None):
    """Structured metrics line (no metrics backend in the stack yet)."""
    usage = usage or {}
    logger.info(
        "ai_call %s",
        json.dumps(
            {
                "kind": kind,
                "outcome": outcome,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            }
        ),
    )


async def trusted_postmortem_context(fingerprint, ticket_id):
    async with SessionLocal() as session:
        incident = (
            await session.execute(
                select(Incident)
                .options(selectinload(Incident.asset))
                .where(Incident.fingerprint == fingerprint)
            )
        ).scalar_one_or_none()
        if incident is None:
            raise ValueError("Postmortem requires an existing incident")
        customer = (incident.tags or {}).get("ninf_customer_name", "").strip()
        if not customer:
            raise ValueError("Postmortem requires an authoritative customer")
        if (
            incident.asset
            and (incident.asset.customer_name or "").casefold() != customer.casefold()
        ):
            raise ValueError("Incident and asset customers disagree")
        if ticket_id is not None and str(ticket_id) != str(
            incident.deskmanager_ticket_id
        ):
            raise ValueError("Ticket does not belong to the incident")
        return {
            "fingerprint": incident.fingerprint,
            "host_id": incident.host_id,
            "host_name": incident.host_name,
            "title": incident.title,
            "trigger_id": incident.trigger_id,
            "trigger_description": incident.sanitized_description or "",
            "severity": incident.severity,
            "status": incident.status,
            "customer_name": customer,
            "deskmanager_ticket_id": incident.deskmanager_ticket_id,
        }
