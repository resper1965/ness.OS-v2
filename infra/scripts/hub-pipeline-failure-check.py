"""Read-only runtime checks; overrides apply only to this disposable process."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from redis.asyncio import Redis

from app.api.routers import pipeline
from app.integrations import pipeline_health as health
from app.integrations.glpi import GLPIClient


async def main():
    healthy = await health.pipeline_health()
    assert healthy["status"] == "ok", healthy
    print(json.dumps({"case": "baseline", "result": healthy}))

    # Closed local endpoint and dummy credentials; no production setting changes.
    unavailable = GLPIClient(
        base_url="http://127.0.0.1:1/apirest.php",
        app_token="readiness-check",
        user_token="readiness-check",
    )
    with patch.object(health, "GLPIClient", return_value=unavailable):
        failed = await health.pipeline_health()
    assert failed["status"] == "degraded" and failed["glpi"]["status"] == "error"
    assert failed["zabbix"]["status"] == "ok"
    with patch.object(pipeline, "pipeline_health", AsyncMock(return_value=failed)):
        portal = await pipeline.get_pipeline_status()
    assert portal["deskmanager"] == portal["glpi"]
    print(json.dumps({"case": "glpi_connection_refused", "result": failed}))

    factory = SimpleNamespace(
        from_url=lambda *args, **kwargs: Redis.from_url(
            "redis://127.0.0.1:1/0", **kwargs
        )
    )
    with patch.object(health, "Redis", factory):
        failed = await health.pipeline_health()
    assert failed["status"] == "degraded" and failed["workers"]["status"] == "error"
    assert failed["glpi"]["status"] == "ok"
    print(json.dumps({"case": "redis_connection_refused", "result": failed}))

    with patch.object(health, "PROBE_TIMEOUT_SECONDS", 0.02):
        timed_out = await health.probe(asyncio.Event().wait)
    assert timed_out["status"] == "error" and timed_out["detail"] == "TimeoutError"
    print(json.dumps({"case": "deadline", "result": timed_out}))


asyncio.run(main())
