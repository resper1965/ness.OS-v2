# -------------------------------------------------------
# n.infraops — Router: Dashboard (Zabbix + Atera)
# -------------------------------------------------------
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis

from app.config import get_settings
from app.core.dependencies import require_noc
from app.dependencies import get_redis
from app.integrations.atera import AteraClient
from app.integrations.glpi import GLPIClient
from app.integrations.zabbix import ZabbixClient
from app.schemas.operational_status import OperationalStatus
from app.services.operational_status import observe_source

logger = logging.getLogger(__name__)
router = APIRouter()


async def _zabbix_summary() -> dict:
    zabbix = ZabbixClient()
    try:
        hosts = await zabbix._call(
            "host.get", {"output": ["hostid"], "filter": {"status": 0}}
        )
        items = await zabbix._call(
            "item.get",
            {
                "output": ["itemid"],
                "filter": {"status": 0},
                "countOutput": True,
                "monitored": True,
            },
        )
        problems_all = await zabbix._call(
            "problem.get",
            {"output": ["eventid", "severity"], "recent": True, "suppressed": False},
        )
        critical = [p for p in (problems_all or []) if int(p.get("severity", 0)) >= 4]
        warning = [p for p in (problems_all or []) if int(p.get("severity", 0)) == 3]
        return {
            "hosts_active": len(hosts or []),
            "items_total": int(items or 0),
            "problems_critical": len(critical),
            "problems_warning": len(warning),
            "problems_total": len(problems_all or []),
        }
    except Exception as exc:
        logger.error("Zabbix summary failed: %s", type(exc).__name__)
        return {"error": "source_unavailable", "degraded": True}


async def _atera_summary() -> dict:
    settings = get_settings()
    key = settings.atera_api_key
    if not key:
        return {"degraded": True, "error": "not_configured"}
    try:
        client = AteraClient(api_key=key)
        return await client.get_dashboard_summary()
    except Exception as exc:
        logger.error("Atera summary failed: %s", type(exc).__name__)
        return {"error": "source_unavailable", "degraded": True}


@router.get(
    "/api/dashboard/sources", tags=["dashboard"], dependencies=[Depends(require_noc)]
)
async def get_operational_sources(redis: Redis = Depends(get_redis)) -> dict:
    """Per-source data and last valid collection for the operator dashboard."""
    settings = get_settings()

    async def zabbix() -> dict:
        result = await _zabbix_summary()
        if result.get("degraded"):
            raise RuntimeError("Zabbix collection failed")
        return result

    async def atera() -> dict:
        result = await _atera_summary()
        if result.get("degraded"):
            raise RuntimeError("Atera collection failed")
        return result

    async def glpi() -> dict:
        return await GLPIClient().readiness_probe()

    statuses = list(
        await asyncio.gather(
            observe_source(
                "zabbix", zabbix, redis, configured=bool(settings.zabbix_api_token)
            ),
            observe_source(
                "atera", atera, redis, configured=bool(settings.atera_api_key)
            ),
            observe_source(
                "glpi",
                glpi,
                redis,
                configured=bool(settings.glpi_app_token and settings.glpi_user_token),
            ),
        )
    )
    statuses.append(
        OperationalStatus(
            status="planned",
            source="wazuh",
            observed_at=datetime.now(timezone.utc),
            stale=True,
            error_code="post_mvp",
        )
    )
    return {"sources": {item.source: item.model_dump(mode="json") for item in statuses}}


@router.get("/api/dashboard/summary", tags=["dashboard"])
async def get_dashboard_summary(_=Depends(require_noc)):
    """Retorna metricas reais do Zabbix para o dashboard. Requer role noc ou admin."""
    result = await _zabbix_summary()
    if result.get("degraded"):
        raise HTTPException(status_code=502, detail="Zabbix indisponível.")
    return result


@router.get("/api/dashboard/unified", tags=["dashboard"])
async def get_unified_summary(_=Depends(require_noc)):
    """
    Resumo unificado: Zabbix + Atera RMM.
    Cada fonte roda em paralelo com timeout de 8s.
    Degrada individualmente. Requer role noc ou admin.
    """
    SOURCE_TIMEOUT = 8.0

    async def _safe(coro, name: str) -> dict:
        try:
            return await asyncio.wait_for(coro, timeout=SOURCE_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning(f"{name} timed out after {SOURCE_TIMEOUT}s")
            return {"degraded": True, "error": "timeout"}
        except Exception as exc:
            logger.error("%s failed: %s", name, type(exc).__name__)
            return {"degraded": True, "error": "source_unavailable"}

    zabbix_data, atera_data = await asyncio.gather(
        _safe(_zabbix_summary(), "zabbix"),
        _safe(_atera_summary(), "atera"),
    )
    return {
        "zabbix": zabbix_data,
        "atera": atera_data,
    }


@router.get("/api/dashboard/problems", tags=["dashboard"])
async def get_dashboard_problems(limit: int = 20, _=Depends(require_noc)):
    """Retorna lista de problemas ativos do Zabbix com info do host."""
    zabbix = ZabbixClient()
    try:
        # Pega problemas ativos (sem selectHosts — não existe em problem.get)
        problems = await zabbix._call(
            "problem.get",
            {
                "output": [
                    "eventid",
                    "name",
                    "severity",
                    "clock",
                    "acknowledged",
                    "objectid",
                ],
                "recent": True,
                "suppressed": False,
                "sortfield": "eventid",
                "sortorder": "DESC",
                "limit": limit,
            },
        )

        if not problems:
            return {"problems": [], "total": 0}

        # Resolve host via trigger (objectid = triggerid para triggers)
        trigger_ids = list({p["objectid"] for p in problems})
        triggers = await zabbix._call(
            "trigger.get",
            {
                "output": ["triggerid"],
                "selectHosts": ["host", "hostid"],
                "triggerids": trigger_ids,
            },
        )

        # Mapa triggerid → nome do host
        trigger_host_map: dict[str, str] = {}
        for t in triggers or []:
            hosts = t.get("hosts", [])
            trigger_host_map[t["triggerid"]] = hosts[0]["host"] if hosts else "unknown"

        severity_map = {
            "0": "not_classified",
            "1": "info",
            "2": "warning",
            "3": "average",
            "4": "high",
            "5": "disaster",
        }

        result = []
        for p in problems:
            result.append(
                {
                    "id": p["eventid"],
                    "title": p["name"],
                    "severity": severity_map.get(
                        str(p.get("severity", "0")), "unknown"
                    ),
                    "severity_level": int(p.get("severity", 0)),
                    "host": trigger_host_map.get(p.get("objectid", ""), "unknown"),
                    "clock": int(p["clock"]),
                    "acknowledged": p.get("acknowledged") == "1",
                }
            )

        return {"problems": result, "total": len(result)}

    except Exception as exc:
        logger.error("Zabbix problems failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Zabbix indisponível.")
