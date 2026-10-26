"""
Router: /api/assets -- Assets unificados (Atera + futuro: Datto, Zabbix)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import get_settings
from app.core.dependencies import get_current_user, require_noc, resolve_tenant_scope
from app.integrations.atera import AteraClient

logger = logging.getLogger(__name__)
router = APIRouter()


def _atera_failure(operation: str, error: Exception) -> HTTPException:
    logger.error("Atera %s failed: %s", operation, type(error).__name__)
    return HTTPException(status_code=502, detail="Atera indisponível.")


@router.get("/cmdb")
async def cmdb_assets(
    tenant_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    user=Depends(get_current_user),
):
    from sqlalchemy import select

    from app.database import SessionLocal
    from app.models import Asset

    scope = resolve_tenant_scope(user, tenant_id)
    async with SessionLocal() as session:
        statement = (
            select(Asset)
            .where(Asset.tags["source"].astext == "zabbix+glpi")
            .order_by(Asset.id)
            .limit(limit)
        )
        if scope:
            statement = statement.where(Asset.customer_id == scope)
        assets = (await session.execute(statement)).scalars().all()
        return {
            "source": "zabbix+glpi",
            "items": [
                {
                    "id": a.id,
                    "host_id": a.zabbix_host_id,
                    "name": a.hostname,
                    "client": a.customer_name,
                    "location": a.location,
                    "glpi_itemtype": a.tags.get("glpi_itemtype"),
                    "glpi_item_id": a.tags.get("glpi_item_id"),
                    "owner": a.tags.get("owner"),
                    "owner_group_id": a.tags.get("glpi_owner_group_id"),
                }
                for a in assets
            ],
            "total": len(assets),
        }


def _atera() -> AteraClient | None:
    key = get_settings().atera_api_key
    return AteraClient(api_key=key) if key else None


@router.get("/summary", dependencies=[Depends(require_noc)])
async def get_assets_summary() -> dict[str, Any]:
    """Resumo consolidado de ativos — Atera + Datto (futuro)."""
    client = _atera()
    if not client:
        return {
            "atera": {
                "total": None,
                "customers": None,
                "alerts": None,
                "status": "unavailable",
                "error_code": "not_configured",
            },
            "datto": {"total": None, "status": "planned"},
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
    except Exception as error:
        raise _atera_failure("summary", error)


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
        raise HTTPException(status_code=503, detail="Atera indisponível.")
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
    except Exception as error:
        raise _atera_failure("asset list", error)


@router.get("/count", dependencies=[Depends(require_noc)])
async def count_assets() -> dict[str, Any]:
    """Contagem rápida de ativos por fonte — usa apenas 1 request por fonte."""
    client = _atera()
    if not client:
        return {
            "atera": None,
            "datto": None,
            "total": None,
            "status": "unavailable",
            "error_code": "not_configured",
        }
    try:
        summary = await client.get_dashboard_summary()
        atera_total = summary.get("agents_total", 0)
        return {
            "atera": atera_total,
            "datto": 0,
            "total": atera_total,
        }
    except Exception as error:
        logger.error("Atera asset count failed: %s", type(error).__name__)
        return {
            "atera": None,
            "datto": None,
            "total": None,
            "status": "unavailable",
            "error_code": "source_unavailable",
        }
