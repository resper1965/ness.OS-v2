"""Small, bounded ledger of integration task outcomes; never stores task payloads."""

import json
import logging
import time

from celery.signals import task_failure, task_retry, task_success
from redis import Redis

from app.config import get_settings

TRACKED = {
    "app.workers.alerts.process_alert_v1",
    "app.workers.tasks.process_ticket_resolution",
}
KEY = "ninf:integration:failures"


def record(sender, state, error=None):
    if getattr(sender, "name", None) not in TRACKED:
        return
    task_id = str(sender.request.id)
    try:
        with Redis.from_url(get_settings().redis_url, decode_responses=True) as redis:
            if state == "success":
                redis.hdel(KEY, task_id)
            else:
                redis.hset(
                    KEY,
                    task_id,
                    json.dumps(
                        {
                            "task": sender.name,
                            "state": state,
                            "error": type(error).__name__,
                            "at": int(time.time()),
                        }
                    ),
                )
                redis.expire(KEY, 30 * 86400)
                # Bound memory even during a sustained failure.
                entries = redis.hgetall(KEY)
                if len(entries) > 1000:
                    oldest = sorted(entries, key=lambda k: json.loads(entries[k])["at"])
                    redis.hdel(KEY, *oldest[: len(entries) - 1000])
    except Exception:
        logging.getLogger(__name__).exception("Integration telemetry unavailable")


@task_failure.connect
def failed(sender=None, exception=None, **kwargs):
    record(sender, "failed", exception)


@task_retry.connect
def retrying(sender=None, reason=None, **kwargs):
    record(sender, "retrying", reason)


@task_success.connect
def succeeded(sender=None, **kwargs):
    record(sender, "success")
