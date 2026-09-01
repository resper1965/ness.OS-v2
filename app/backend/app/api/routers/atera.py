"""
Router: /api/rmm/atera -- Atera RMM v3
Expoe clientes, agentes e alertas Atera para o dashboard.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import get_settings
from app.core.dependencies import require_noc
from app.integrations.atera import AteraClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rmm/atera", tags=["rmm-atera"])


def _client() -> AteraClient:
    settings = get_settings()
    key = settings.atera_api_key
    if not key:
        raise HTTPException(503, "NINF_ATERA_API_KEY not configured")
    return AteraClient(api_key=key)


@router.get("/customers", dependencies=[Depends(require_noc)])
async def list_customers() -> dict[str, Any]:
    """Lista todos os clientes Atera (21 clientes)."""
    try:
        client = _client()
        customers = await client.list_customers()
        return {"source": "atera", "total": len(customers), "items": customers}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Atera list_customers: {e}")
        raise HTTPException(502, str(e))


@router.get("/agents", dependencies=[Depends(require_noc)])
async def list_agents(
    customer_id: int | None = Query(None, description="Filtrar por CustomerID Atera"),
) -> dict[str, Any]:
    """Lista agentes/endpoints. Sem customer_id retorna todos (1637 agentes)."""
    try:
        client = _client()
        if customer_id:
            agents = await client.list_agents_by_customer(customer_id=customer_id)
        else:
            agents = await client.list_agents()
        return {
            "source": "atera",
            "customer_id": customer_id,
            "total": len(agents),
            "items": agents,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Atera list_agents: {e}")
        raise HTTPException(502, str(e))


@router.get("/alerts", dependencies=[Depends(require_noc)])
async def list_alerts(
    severity: str | None = Query(None, description="Information|Warning|Critical"),
) -> dict[str, Any]:
    """Lista alertas Atera, opcionalmente filtrados por severidade."""
    try:
        client = _client()
        alerts = await client.list_alerts()
        if severity:
            alerts = [
                a for a in alerts if a.get("Severity", "").lower() == severity.lower()
            ]
        return {
            "source": "atera",
            "severity_filter": severity,
            "total": len(alerts),
            "items": alerts,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Atera list_alerts: {e}")
        raise HTTPException(502, str(e))


@router.get("/summary", dependencies=[Depends(require_noc)])
async def atera_summary() -> dict[str, Any]:
    """Resumo consolidado Atera para o dashboard."""
    try:
        client = _client()
        return await client.get_dashboard_summary()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Atera summary: {e}")
        raise HTTPException(502, str(e))
