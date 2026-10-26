"""Allowlisted provider context and authoritative post-incident identity."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.sanitizer import sanitize_dict
from app.database import SessionLocal
from app.models import Incident

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
