"""
Router: /api/assets -- Assets unificados (Atera + futuro: Datto, Zabbix)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import get_settings
from app.core.dependencies import require_noc
from app.integrations.atera import AteraClient

logger = logging.getLogger(__name__)
router = APIRouter()


def _atera() -> AteraClient | None:
    key = get_settings().atera_api_key
    return AteraClient(api_key=key) if key else None


@router.get("/summary", dependencies=[Depends(require_noc)])
async def get_assets_summary() -> dict[str, Any]:
    """Resumo consolidado de ativos — Atera + Datto (futuro)."""
    client = _atera()
    if not client:
        return {
            "atera": {"degraded": True, "error": "API key not configured"},
            "datto": {"total": 0},
        }
    try:
        summary = await client.get_dashboard_summary()
        return {
            "atera": {
                "total": summary.get("agents_total", 0),
                "customers": summary.get("customers_total", 0),
                "alerts": summary.get("alerts_total", 0),
            },
            "datto": {"total": 0, "note": "pending credentials"},
        }
    except Exception as e:
        logger.error(f"Assets summary error: {e}")
        raise HTTPException(502, str(e))


@router.get("", dependencies=[Depends(require_noc)])
async def list_assets(
    customer_id: int | None = Query(None, description="Filtrar por cliente Atera"),
    source: str = Query("atera", description="atera | all"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """
    Lista ativos normalizados.
    Atera Agent → Asset unificado com: id, name, customer, os, ip, status, source.
    """
    client = _atera()
    if not client:
        raise HTTPException(503, "NINF_ATERA_API_KEY not configured")
    try:
        if customer_id:
            agents = await client.list_agents_by_customer(customer_id)
        else:
            # Para listagem geral, limitar a 1ª página para não paginar 1.637 agentes
            body = await client._get_page_one("/agents", page_size=limit)
            agents = body.get("items", [])

        normalized = []
        for a in agents:
            normalized.append(
                {
                    "id": a.get("AgentID"),
                    "name": a.get("MachineName") or a.get("AgentName", ""),
                    "customer": a.get("CustomerName", ""),
                    "customer_id": a.get("CustomerID"),
                    "os": a.get("OS") or a.get("OSType", ""),
                    "os_type": (
                        "windows"
                        if "windows" in (a.get("OS", "") or "").lower()
                        else "linux"
                    ),
                    "ip": a.get("IpAddresses") or a.get("PublicIP", ""),
                    "status": (
                        "active"
                        if a.get("Online") or a.get("OnlineStatus") == "Online"
                        else "offline"
                    ),
                    "rmm_provider": "atera",
                    "source": "atera",
                }
            )

        return {
            "source": "atera",
            "customer_id": customer_id,
            "total": len(normalized),
            "items": normalized,
        }
    except Exception as e:
        logger.error(f"Assets list error: {e}")
        raise HTTPException(502, str(e))


@router.get("/count", dependencies=[Depends(require_noc)])
async def count_assets() -> dict[str, Any]:
    """Contagem rápida de ativos por fonte — usa apenas 1 request por fonte."""
    client = _atera()
    if not client:
        return {"atera": 0, "datto": 0, "total": 0, "degraded": True}
    try:
        summary = await client.get_dashboard_summary()
        atera_total = summary.get("agents_total", 0)
        return {
            "atera": atera_total,
            "datto": 0,
            "total": atera_total,
        }
    except Exception as e:
        logger.error(f"Assets count error: {e}")
        return {"atera": 0, "datto": 0, "total": 0, "error": str(e)}
