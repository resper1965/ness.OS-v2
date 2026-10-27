"""Readiness and unresolved delivery failures for the production hub/GLPI flow."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from time import monotonic
from urllib.parse import urlsplit

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
MAX_QUEUE_AGE_SECONDS = 300
MAX_SOURCE_AGE_SECONDS = 900


def _broker_read_url():
    connection = celery_app.connection_for_read()
    try:
        return connection.as_uri(include_password=True)
    finally:
        connection.release()


def _oldest_message_age(raw_message, now):
    try:
        published_at = float(json.loads(raw_message)["headers"]["ninf_published_at"])
        return max(0, int(now - published_at))
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


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
    clients = []
    checked = datetime.now(timezone.utc)
    checked_at = checked.isoformat()
    try:
        broker_url = _broker_read_url()
        broker_db = int(urlsplit(broker_url).path.strip("/") or 0)
        queue_redis = Redis.from_url(
            broker_url,
            decode_responses=True,
            socket_connect_timeout=4,
            socket_timeout=4,
        )
        clients.append(queue_redis)
        telemetry_redis = Redis.from_url(
            get_settings().redis_url,
            decode_responses=True,
            socket_connect_timeout=4,
            socket_timeout=4,
        )
        clients.append(telemetry_redis)
        queues = {}
        ages = {}
        for queue in ("alerts.primary", "alerts.deferred", "ml"):
            depth = await queue_redis.llen(queue)
            queues[queue] = depth
            if depth:
                # ponytail: current tasks use default Redis priority; inspect priority buckets if that changes.
                raw_oldest = await queue_redis.lindex(queue, -1)
                if raw_oldest is None:
                    depth = await queue_redis.llen(queue)
                    queues[queue] = depth
                ages[queue] = (
                    _oldest_message_age(raw_oldest, checked.timestamp()) if depth else 0
                )
            else:
                ages[queue] = 0
        records = [json.loads(v) for v in (await telemetry_redis.hgetall(KEY)).values()]
        replies = await asyncio.to_thread(
            lambda: celery_app.control.inspect(timeout=3).active_queues()
        )
        workers_by_queue = {queue: 0 for queue in queues}
        for node_queues in (replies or {}).values():
            for active_queue in node_queues:
                queue = active_queue["name"]
                if queue in workers_by_queue:
                    workers_by_queue[queue] += 1
        missing = sorted(
            queue for queue, count in workers_by_queue.items() if not count
        )
        failed = sum(r["state"] == "failed" for r in records)
        retrying = sum(r["state"] == "retrying" for r in records)
        queue_health = []
        for queue, depth in queues.items():
            age = ages[queue]
            error = None
            status = "ok"
            if not workers_by_queue[queue]:
                status, error = "error", "missing_consumer"
            elif depth > 100:
                status, error = "degraded", "queue_backlog_high"
            elif depth and age is None:
                status, error = "degraded", "publish_timestamp_missing"
            elif age is not None and age > MAX_QUEUE_AGE_SECONDS:
                status, error = "degraded", "oldest_message_too_old"
            queue_health.append(
                {
                    "queue": queue,
                    "redis_db": broker_db,
                    "depth": depth,
                    "oldest_age_seconds": age,
                    "workers_seen": workers_by_queue[queue],
                    "status": status,
                    "checked_at": checked_at,
                    "error": error,
                }
            )
        return {
            "status": (
                "error"
                if missing or failed
                else (
                    "degraded"
                    if retrying or any(q["status"] == "degraded" for q in queue_health)
                    else "ok"
                )
            ),
            "queues": queues,
            "queue_health": queue_health,
            "redis_db": broker_db,
            "workers_seen": len(replies or {}),
            "checked_at": checked_at,
            "oldest_age_seconds": (
                max(ages.values())
                if all(age is not None for age in ages.values())
                else None
            ),
            "error": (
                ",".join(sorted({q["error"] for q in queue_health if q["error"]}))
                or ("failed_tasks_present" if failed else None)
            ),
            "missing_consumers": missing,
            "failed_tasks": failed,
            "retrying_tasks": retrying,
            "detail": f"workers:{len(replies or {})} failures:{failed} retries:{retrying}",
        }
    except Exception as exc:
        return {
            "status": "error",
            "checked_at": checked_at,
            "error": type(exc).__name__,
            "detail": type(exc).__name__,
        }
    finally:
        await asyncio.gather(
            *(client.aclose() for client in clients), return_exceptions=True
        )


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


async def with_freshness(name, result, cache, now):
    """Add scope, last success, age and last error; only a healthy probe counts as success."""
    key = f"ninf:pipeline:last-success:{name}"
    last = now if result["status"] == "ok" else None
    try:
        if last:
            await cache.set(key, now.isoformat())
        else:
            last = datetime.fromisoformat(await cache.get(key))
    except Exception:
        pass  # unknown last success is reported as stale below
    age = max(0, int((now - last).total_seconds())) if last else None
    return {
        **result,
        # Platform-wide credentials: these probes do not check any single tenant.
        "scope": "global",
        "last_success_at": last.isoformat() if last else None,
        "freshness_seconds": age,
        "stale": age is None or age > MAX_SOURCE_AGE_SECONDS,
        "last_error": None if result["status"] == "ok" else result.get("detail"),
    }


async def pipeline_health():
    started = monotonic()
    zabbix, glpi, workers, delivery = await asyncio.gather(
        probe(ZabbixClient().readiness_probe),
        probe(GLPIClient().readiness_probe),
        probe(workers_health, readiness=False),
        probe(incident_health, readiness=False),
    )
    now = datetime.now(timezone.utc)
    cache = Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        zabbix, glpi, workers, delivery = [
            await with_freshness(name, value, cache, now)
            for name, value in (
                ("zabbix", zabbix),
                ("glpi", glpi),
                ("workers", workers),
                ("delivery", delivery),
            )
        ]
    finally:
        await cache.aclose()
    return {
        "status": (
            "ok"
            if all(x["status"] == "ok" for x in (zabbix, glpi, workers, delivery))
            else "degraded"
        ),
        # Not a container healthcheck: /ready stays independent of external sources.
        "ready": not any(x["stale"] for x in (zabbix, glpi, workers, delivery)),
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
