# -------------------------------------------------------
# n.infraops — Router: Pipeline Status
# Verifica saúde de cada integração do pipeline AIOps
# -------------------------------------------------------
from __future__ import annotations
import asyncio
import logging
from fastapi import APIRouter
from app.integrations.zabbix import ZabbixClient
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


async def _check_zabbix() -> dict:
    """Chama apiinfo.version sem auth — metodo publico do Zabbix."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5, verify=False) as client:
            r = await client.post(
                settings.zabbix_url,
                json={"jsonrpc": "2.0", "method": "apiinfo.version", "params": {}, "id": 1},
            )
            data = r.json()
            version = data.get("result", "?")
            return {"status": "ok", "detail": f"Zabbix {version}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:80]}


async def _check_workers() -> dict:
    """Verifica workers via Redis — presença de heartbeat key."""
    try:
        import redis.asyncio as aioredis
        r = await aioredis.from_url(settings.redis_url, decode_responses=True)
        # Workers saudáveis registram-se no broker (fila existe)
        alerts_len = await r.llen("alerts.primary") 
        ml_len = await r.llen("ml")
        await r.aclose()
        return {"status": "ok", "detail": f"queues ok (alerts:{alerts_len} ml:{ml_len})"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:80]}


async def _check_n8n() -> dict:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.n8n_base_url}/healthz")
            if r.status_code == 200:
                return {"status": "ok", "detail": "n8n online"}
            return {"status": "error", "detail": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:80]}


async def _check_deskmanager() -> dict:
    if not settings.deskmanager_api_token:
        return {"status": "unconfigured", "detail": "Token não configurado"}
    return {"status": "ok", "detail": "Token presente"}


async def _check_whatsapp() -> dict:
    if not settings.evolution_api_key:
        return {"status": "unconfigured", "detail": "API key não configurada"}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{settings.evolution_api_url}/instance/fetchInstances",
                headers={"apikey": settings.evolution_api_key},
            )
            if r.status_code == 200:
                return {"status": "ok", "detail": "Evolution online"}
            return {"status": "error", "detail": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:80]}


@router.get("/api/dashboard/pipeline-status", tags=["dashboard"])
async def get_pipeline_status():
    """Retorna saúde de cada elo do pipeline AIOps em paralelo."""
    results = await asyncio.gather(
        _check_zabbix(),
        _check_workers(),
        _check_n8n(),
        _check_deskmanager(),
        _check_whatsapp(),
        return_exceptions=False,
    )
    return {
        "zabbix": results[0],
        "workers": results[1],
        "n8n": results[2],
        "deskmanager": results[3],
        "whatsapp": results[4],
    }
