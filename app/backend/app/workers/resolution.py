"""Authoritative GLPI solution import, serialized per ticket by the task wrapper."""

import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.integrations.glpi import GLPIClient
from app.integrations.zabbix import ZabbixClient
from app.models import Incident, IncidentAction, IncidentReport


async def resolve_ticket(ticket_id: str, redis) -> dict:
    from app.workers.alerts import resolve_glpi_entity_id

    async with SessionLocal() as session:
        incident = (
            await session.execute(
                select(Incident).where(Incident.deskmanager_ticket_id == ticket_id)
            )
        ).scalar_one_or_none()
        if incident is None:
            return {"status": "not_found", "ticket_id": ticket_id}
        tags = dict(incident.tags or {})
        entity_id = resolve_glpi_entity_id(tags.get("ninf_customer_name", ""))
        glpi = GLPIClient()
        try:
            resolution = await glpi.ticket_resolution(
                int(ticket_id), entity_id, incident.fingerprint
            )
        finally:
            await glpi.kill_session()
        if not resolution["resolved"]:
            return {
                "status": "ignored",
                "reason": "ticket_not_resolved",
                "ticket_id": ticket_id,
            }

        solution = resolution["solution"]
        solution_id = resolution["solution_id"]
        previous_status = incident.status
        imported = (
            tags.get("glpi_solution_id") != solution_id or previous_status != "resolved"
        )
        already_synced = (
            tags.get("glpi_solution_id") == solution_id
            and tags.get("resolution_sync_status") == "synced"
        )
        if solution and tags.get("glpi_solution_id") != solution_id:
            report = (
                await session.execute(
                    select(IncidentReport).where(
                        IncidentReport.deskmanager_ticket_id == ticket_id
                    )
                )
            ).scalar_one_or_none()
            if report:
                report.markdown_report += (
                    f"\n\n## Solução GLPI #{solution_id}\n{solution}\n"
                )
                report.corrective_actions = [
                    *(report.corrective_actions or []),
                    solution,
                ]
                # An embedding for the old text must not be presented as current.
                report.embedding = None
        now = datetime.now(timezone.utc).isoformat()
        tags.update(
            glpi_solution_id=solution_id,
            glpi_solution=solution,
            glpi_resolved_at=tags.get("glpi_resolved_at") or now,
            resolution_sync_status="pending",
        )
        incident.tags = tags
        incident.status = "resolved"
        if imported:
            session.add(
                IncidentAction(
                    incident_id=incident.id,
                    actor_source="glpi",
                    action="glpi_resolution_imported",
                    previous_status=previous_status,
                    new_status="resolved",
                    previous_assignee_id=getattr(incident, "assigned_user_id", None),
                    new_assignee_id=getattr(incident, "assigned_user_id", None),
                    note=f"ticket={ticket_id} solution={solution_id}",
                )
            )
        await session.commit()

        event_id = tags.get("ninf_zabbix_event_id")
        if not event_id:
            raise ValueError("Incident has no original Zabbix event")
        ack = await ZabbixClient().acknowledge_resolution_once(
            event_id, ticket_id, solution
        )
        incident.tags = {
            **tags,
            "resolution_sync_status": "synced",
            "resolution_synced_at": now,
        }
        if not already_synced:
            session.add(
                IncidentAction(
                    incident_id=incident.id,
                    actor_source="zabbix",
                    action="resolution_acknowledged",
                    previous_status=incident.status,
                    new_status=incident.status,
                    previous_assignee_id=getattr(incident, "assigned_user_id", None),
                    new_assignee_id=getattr(incident, "assigned_user_id", None),
                    note=f"event={event_id} result={ack}",
                )
            )
        await session.commit()
        redis.publish(
            "ninf_incidents",
            json.dumps(
                {
                    "id": str(incident.id),
                    "fingerprint": incident.fingerprint,
                    "tenant_id": tags["ninf_customer_name"].lower().strip(),
                    "status": "resolved",
                    "pipeline_stage": "resolved",
                    "ticket_id": ticket_id,
                    "solution": solution,
                    "updated_at": now,
                }
            ),
        )
        return {
            "status": "success",
            "ticket_id": ticket_id,
            "fingerprint": incident.fingerprint,
            "zabbix_status": ack,
        }
