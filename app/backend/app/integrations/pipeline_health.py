"""Readiness and unresolved delivery failures for the production hub/GLPI flow."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from time import monotonic

from redis.asyncio import Redis
from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.integrations.glpi import GLPIClient
from app.integrations.zabbix import ZabbixClient
from app.models import Incident
from app.workers.celery_app import celery_app
from app.workers.telemetry import KEY

PROBE_TIMEOUT_SECONDS = 20


async def probe(call, *, readiness=True):
    started = monotonic()
    try:
        result = await asyncio.wait_for(call(), timeout=PROBE_TIMEOUT_SECONDS)
        if not isinstance(result, dict):
            raise ValueError("Invalid probe response")
        if readiness:
            if result.get("status") != "ready":
                raise ValueError("Dependency did not confirm readiness")
            result = {"status": "ok"}
        elif result.get("status") not in {"ok", "error", "degraded"}:
            raise ValueError("Unknown health status")
    except Exception as exc:
        result = {"status": "error", "detail": type(exc).__name__}
    return {**result, "duration_ms": round((monotonic() - started) * 1000, 1)}


async def workers_health():
    redis = Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=4,
        socket_timeout=4,
    )
    try:
        queues = {
            q: await redis.llen(q) for q in ("alerts.primary", "alerts.deferred", "ml")
        }
        records = [json.loads(v) for v in (await redis.hgetall(KEY)).values()]
        replies = await asyncio.to_thread(
            lambda: celery_app.control.inspect(timeout=3).active_queues()
        )
        consumed = {q["name"] for node in (replies or {}).values() for q in node}
        missing = sorted(set(queues) - consumed)
        failed = sum(r["state"] == "failed" for r in records)
        retrying = sum(r["state"] == "retrying" for r in records)
        return {
            "status": (
                "error"
                if missing or failed
                else ("degraded" if max(queues.values()) > 100 or retrying else "ok")
            ),
            "queues": queues,
            "missing_consumers": missing,
            "failed_tasks": failed,
            "retrying_tasks": retrying,
            "detail": f"workers:{len(replies or {})} failures:{failed} retries:{retrying}",
        }
    except Exception as exc:
        return {"status": "error", "detail": type(exc).__name__}
    finally:
        await redis.aclose()


async def incident_health():
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    try:
        async with SessionLocal() as session:
            missing = await session.scalar(
                select(func.count())
                .select_from(Incident)
                .where(
                    Incident.tags.has_key("ninf_zabbix_event_id"),
                    Incident.deskmanager_ticket_id.is_(None),
                    Incident.created_at < cutoff,
                )
            )
            pending = await session.scalar(
                select(func.count())
                .select_from(Incident)
                .where(
                    Incident.tags["resolution_sync_status"].astext == "pending",
                    Incident.updated_at < cutoff,
                )
            )
        return {
            "status": "error" if missing or pending else "ok",
            "incidents_without_ticket": missing,
            "resolutions_pending": pending,
            "detail": f"Sem ticket há mais de 5 min: {missing}; resoluções pendentes: {pending}",
        }
    except Exception as exc:
        return {"status": "error", "detail": type(exc).__name__}


async def pipeline_health():
    started = monotonic()
    zabbix, glpi, workers, delivery = await asyncio.gather(
        probe(ZabbixClient().readiness_probe),
        probe(GLPIClient().readiness_probe),
        probe(workers_health, readiness=False),
        probe(incident_health, readiness=False),
    )
    return {
        "status": (
            "ok"
            if all(x["status"] == "ok" for x in (zabbix, glpi, workers, delivery))
            else "degraded"
        ),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round((monotonic() - started) * 1000, 1),
        "zabbix": zabbix,
        "glpi": glpi,
        "workers": workers,
        "delivery": delivery,
    }


if __name__ == "__main__":
    result = asyncio.run(pipeline_health())
    print(json.dumps(result))
    raise SystemExit(0 if result["status"] == "ok" else 1)
