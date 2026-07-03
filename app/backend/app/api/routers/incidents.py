# -------------------------------------------------------
# n.infraops — Router: Incidents
# Lista incidentes do PostgreSQL com pipeline_stage calculado
# -------------------------------------------------------
from __future__ import annotations
import logging
from fastapi import APIRouter, Query
from sqlalchemy import select, desc
from app.database import SessionLocal
from app.models import Incident

logger = logging.getLogger(__name__)
router = APIRouter()

# Mapeamento severity → label
SEVERITY_LABEL = {
    0: "not_classified", 1: "info", 2: "warning",
    3: "average", 4: "high", 5: "disaster",
}


def _pipeline_stage(incident: Incident) -> str:
    """Calcula em qual etapa do pipeline o incidente está."""
    # Por enquanto derivado dos campos existentes.
    # Quando DeskManager e n8n forem integrados, estes campos serão persistidos.
    if incident.status == "resolved":
        return "postmortem"
    if incident.alert_count and incident.alert_count > 0:
        # TODO: verificar se ticket_id existe (campo futuro)
        return "incident_created"
    return "detected"


@router.get("/api/incidents", tags=["incidents"])
async def list_incidents(
    limit: int = Query(default=20, le=100),
    status: str | None = Query(default=None),
):
    """Retorna lista de incidentes com stage do pipeline."""
    async with SessionLocal() as session:
        stmt = select(Incident).order_by(desc(Incident.last_seen)).limit(limit)
        if status:
            stmt = stmt.where(Incident.status == status)
        result = await session.execute(stmt)
        incidents = result.scalars().all()

        return {
            "incidents": [
                {
                    "id": str(inc.id),
                    "title": inc.title,
                    "severity": SEVERITY_LABEL.get(inc.severity or 0, "unknown"),
                    "severity_level": inc.severity or 0,
                    "host_name": inc.host_name or "unknown",
                    "status": inc.status,
                    "alert_count": inc.alert_count or 1,
                    "first_seen": inc.first_seen.isoformat() if inc.first_seen else None,
                    "last_seen": inc.last_seen.isoformat() if inc.last_seen else None,
                    "pipeline_stage": _pipeline_stage(inc),
                }
                for inc in incidents
            ],
            "total": len(incidents),
        }
