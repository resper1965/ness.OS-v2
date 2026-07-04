# -------------------------------------------------------
# n.infraops — Router: Dashboard (Zabbix + Atera + RocketCyber)
# -------------------------------------------------------
from __future__ import annotations
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from app.config import get_settings
from app.integrations.zabbix import ZabbixClient
from app.integrations.atera import AteraClient
from app.integrations.rocketcyber import RocketCyberClient

logger = logging.getLogger(__name__)
router = APIRouter()


async def _zabbix_summary() -> dict:
    zabbix = ZabbixClient()
    try:
        hosts = await zabbix._call("host.get", {"output": ["hostid"], "filter": {"status": 0}})
        items = await zabbix._call("item.get", {"output": ["itemid"], "filter": {"status": 0}, "countOutput": True, "monitored": True})
        problems_all = await zabbix._call("problem.get", {"output": ["eventid", "severity"], "recent": True, "suppressed": False})
        critical = [p for p in (problems_all or []) if int(p.get("severity", 0)) >= 4]
        warning  = [p for p in (problems_all or []) if int(p.get("severity", 0)) == 3]
        return {
            "hosts_active": len(hosts or []),
            "items_total": int(items or 0),
            "problems_critical": len(critical),
            "problems_warning": len(warning),
            "problems_total": len(problems_all or []),
        }
    except Exception as e:
        logger.error("Zabbix summary error: %s", e)
        return {"error": str(e), "degraded": True}


async def _atera_summary() -> dict:
    settings = get_settings()
    key = settings.atera_api_key
    if not key:
        return {"degraded": True, "error": "API key not configured"}
    try:
        client = AteraClient(api_key=key)
        return await client.get_dashboard_summary()
    except Exception as e:
        logger.error("Atera summary error: %s", e)
        return {"error": str(e), "degraded": True}


async def _rocketcyber_summary() -> dict:
    settings = get_settings()
    key = settings.rocketcyber_api_key
    if not key:
        return {"degraded": True, "error": "API key not configured"}
    try:
        client = RocketCyberClient(api_key=key)
        return await client.get_dashboard_summary()
    except Exception as e:
        logger.error("RocketCyber summary error: %s", e)
        return {"error": str(e), "degraded": True}


@router.get("/api/dashboard/summary", tags=["dashboard"])
async def get_dashboard_summary():
    """Retorna métricas reais do Zabbix para o dashboard (compatibilidade)."""
    result = await _zabbix_summary()
    if result.get("degraded"):
        raise HTTPException(status_code=502, detail=f"Zabbix API error: {result.get('error')}")
    return result


@router.get("/api/dashboard/unified", tags=["dashboard"])
async def get_unified_summary():
    """
    Resumo unificado: Zabbix + Atera RMM + RocketCyber SOC.
    Cada fonte roda em paralelo e degrada individualmente sem quebrar o todo.
    """
    zabbix_data, atera_data, rocket_data = await asyncio.gather(
        _zabbix_summary(),
        _atera_summary(),
        _rocketcyber_summary(),
        return_exceptions=False,
    )
    return {
        "zabbix": zabbix_data,
        "atera": atera_data,
        "rocketcyber": rocket_data,
    }



@router.get("/api/dashboard/problems", tags=["dashboard"])
async def get_dashboard_problems(limit: int = 20):
    """Retorna lista de problemas ativos do Zabbix com info do host."""
    zabbix = ZabbixClient()
    try:
        # Pega problemas ativos (sem selectHosts — não existe em problem.get)
        problems = await zabbix._call("problem.get", {
            "output": ["eventid", "name", "severity", "clock", "acknowledged", "objectid"],
            "recent": True,
            "suppressed": False,
            "sortfield": "eventid",
            "sortorder": "DESC",
            "limit": limit,
        })

        if not problems:
            return {"problems": [], "total": 0}

        # Resolve host via trigger (objectid = triggerid para triggers)
        trigger_ids = list({p["objectid"] for p in problems})
        triggers = await zabbix._call("trigger.get", {
            "output": ["triggerid"],
            "selectHosts": ["host", "hostid"],
            "triggerids": trigger_ids,
        })

        # Mapa triggerid → nome do host
        trigger_host_map: dict[str, str] = {}
        for t in (triggers or []):
            hosts = t.get("hosts", [])
            trigger_host_map[t["triggerid"]] = hosts[0]["host"] if hosts else "unknown"

        severity_map = {
            "0": "not_classified", "1": "info", "2": "warning",
            "3": "average", "4": "high", "5": "disaster",
        }

        result = []
        for p in problems:
            result.append({
                "id": p["eventid"],
                "title": p["name"],
                "severity": severity_map.get(str(p.get("severity", "0")), "unknown"),
                "severity_level": int(p.get("severity", 0)),
                "host": trigger_host_map.get(p.get("objectid", ""), "unknown"),
                "clock": int(p["clock"]),
                "acknowledged": p.get("acknowledged") == "1",
            })

        return {"problems": result, "total": len(result)}

    except Exception as e:
        logger.error("Erro ao buscar problemas do Zabbix: %s", e)
        raise HTTPException(status_code=502, detail=f"Zabbix API error: {str(e)}")
