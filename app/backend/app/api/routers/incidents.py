# -------------------------------------------------------
# n.infraops — Router: Incidents
# Lista incidentes do PostgreSQL com pipeline_stage calculado
# -------------------------------------------------------
from __future__ import annotations
import logging
from fastapi import APIRouter, Query, BackgroundTasks
from sqlalchemy import select, desc
from app.database import SessionLocal
from app.models import Incident
from app.models.schemas import IncidentAnalyzeRequest

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


async def _run_incident_analysis(request: IncidentAnalyzeRequest):
    """Executa a análise de causa raiz via Gemini em background e aciona o n8n."""
    from app.config import get_settings
    from app.integrations.gemini import generate_postmortem
    import httpx
    
    settings = get_settings()
    
    try:
        # 1. Obter dados brutos do incidente enviado pelo Keep
        incident_data = request.incident_data
        
        # TODO: Buscar métricas reais no TimescaleDB e logs reais
        # Mocking para v1.0
        metrics_mock = [{"metric": "cpu_load", "value": 95.5, "timestamp": "2026-07-06T12:00:00Z"}]
        logs_mock = ["ERROR: connection timeout to database", "WARN: high memory usage detected"]
        
        # 2. Chamar o Gemini para gerar o PostMortem
        logger.info(f"Iniciando análise Gemini para incidente {incident_data.get('fingerprint', 'unknown')}")
        postmortem = generate_postmortem(
            incident=incident_data,
            metrics=metrics_mock,
            related_logs=logs_mock
        )
        
        # 3. Disparar webhook para o n8n (/webhook/postmortem-ready)
        n8n_url = f"{settings.n8n_base_url.rstrip('/')}{settings.n8n_webhook_postmortem}"
        payload = {
            "ticket_id": request.ticket_id,
            "incident_fingerprint": postmortem.incident_fingerprint,
            "summary": postmortem.summary,
            "root_cause": postmortem.root_cause,
            "markdown_report": postmortem.markdown_report,
            "blast_radius": postmortem.blast_radius,
            "corrective_actions": postmortem.corrective_actions
        }
        
        logger.info(f"Enviando PostMortem para o n8n: {n8n_url}")
        async with httpx.AsyncClient() as client:
            resp = await client.post(n8n_url, json=payload, timeout=10.0)
            resp.raise_for_status()
            logger.info("PostMortem enviado ao n8n com sucesso.")
            
    except Exception as exc:
        logger.error(f"Falha na análise de incidente em background: {exc}")


@router.post("/api/incident/analyze", tags=["incidents"], status_code=202)
async def analyze_incident(
    request: IncidentAnalyzeRequest,
    background_tasks: BackgroundTasks
):
    """
    Recebe um alerta correlacionado (ex: via Keep AIOps), 
    adiciona tarefa em background para gerar RCA no Gemini 
    e retorna 202 Accepted.
    """
    background_tasks.add_task(_run_incident_analysis, request)
    return {"status": "accepted", "message": "Análise de causa raiz iniciada em background."}
