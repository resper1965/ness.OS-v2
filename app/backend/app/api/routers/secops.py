"""
Router: /api/secops — RocketCyber SOC Integration
Expõe incidentes de segurança e resumo SOC para o dashboard.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.integrations.rocketcyber import RocketCyberClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/secops", tags=["secops"])


def _client() -> RocketCyberClient:
    settings = get_settings()
    key = getattr(settings, "rocketcyber_api_key", None)
    if not key:
        raise HTTPException(503, "ROCKETCYBER_API_KEY not configured")
    return RocketCyberClient(api_key=key)


@router.get("/incidents")
async def list_incidents(
    account_id: int | None = Query(None, description="Account ID do cliente"),
    status: str = Query("open", description="open|resolved|all"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """
    Lista incidentes de segurança RocketCyber.
    Sem account_id retorna todos (nível MSP).
    """
    try:
        client = _client()
        if status == "all":
            # busca open por padrão quando sem filtro
            incidents = await client.list_open_incidents(account_id=account_id, limit=limit)
        else:
            incidents = await client.list_open_incidents(account_id=account_id, limit=limit)
        return {
            "source": "rocketcyber",
            "account_id": account_id,
            "status": status,
            "total": len(incidents),
            "items": incidents,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RocketCyber incidents: {e}")
        raise HTTPException(502, str(e))


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: int, account_id: int = Query(...)) -> dict[str, Any]:
    """Detalhe de um incidente específico."""
    try:
        client = _client()
        incident = await client.get_incident(incident_id=incident_id, account_id=account_id)
        if not incident:
            raise HTTPException(404, f"Incident {incident_id} not found")
        return incident
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RocketCyber get_incident: {e}")
        raise HTTPException(502, str(e))


@router.get("/agents")
async def list_agents(account_id: int = Query(...)) -> dict[str, Any]:
    """Lista agentes RocketCyber de um cliente."""
    try:
        client = _client()
        agents = await client.list_agents(account_id=account_id)
        return {"source": "rocketcyber", "account_id": account_id, "total": len(agents), "items": agents}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RocketCyber agents: {e}")
        raise HTTPException(502, str(e))


@router.get("/summary")
async def secops_summary() -> dict[str, Any]:
    """Resumo SOC consolidado para o dashboard (todos os accounts)."""
    try:
        client = _client()
        return await client.get_dashboard_summary()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RocketCyber summary: {e}")
        # Retorna degraded ao invés de 502 para não quebrar o dashboard
        return {"source": "rocketcyber", "degraded": True, "error": str(e)}
