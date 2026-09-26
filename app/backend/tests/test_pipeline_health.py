import asyncio
from unittest.mock import AsyncMock

import pytest

from app.api.routers import pipeline
from app.integrations import pipeline_health as health
from app.integrations.glpi import GLPIClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response", [None, {}, {"status": "error"}, {"status": "unknown"}]
)
async def test_readiness_must_be_explicit(response):
    result = await health.probe(AsyncMock(return_value=response))
    assert result["status"] == "error"
    assert result["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_probe_deadline_cancels_stalled_dependency(monkeypatch):
    monkeypatch.setattr(health, "PROBE_TIMEOUT_SECONDS", 0.02)
    cancelled = asyncio.Event()

    async def stalled():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    result = await health.probe(stalled)
    assert result["status"] == "error" and result["detail"] == "TimeoutError"
    assert cancelled.is_set()
    assert result["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_dependency_errors_do_not_expose_credentials():
    result = await health.probe(AsyncMock(side_effect=RuntimeError("secret-token")))
    assert result["detail"] == "RuntimeError"
    assert "secret-token" not in str(result)


@pytest.mark.asyncio
async def test_degraded_workers_cannot_become_healthy(monkeypatch):
    monkeypatch.setattr(
        health.ZabbixClient,
        "readiness_probe",
        AsyncMock(return_value={"status": "ready"}),
    )
    monkeypatch.setattr(
        health.GLPIClient,
        "readiness_probe",
        AsyncMock(return_value={"status": "ready"}),
    )
    monkeypatch.setattr(
        health,
        "workers_health",
        AsyncMock(return_value={"status": "degraded", "queues": {"ml": 101}}),
    )
    monkeypatch.setattr(
        health, "incident_health", AsyncMock(side_effect=ConnectionError("db-password"))
    )
    result = await health.pipeline_health()
    assert result["status"] == "degraded"
    assert result["workers"]["queues"] == {"ml": 101}
    assert result["delivery"]["status"] == "error"
    assert "db-password" not in str(result)
    for key in ("zabbix", "glpi", "workers", "delivery"):
        assert result[key]["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_portal_retains_glpi_failure_detail(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "pipeline_health",
        AsyncMock(
            return_value={
                "glpi": {"status": "error", "detail": "TimeoutError", "duration_ms": 20}
            }
        ),
    )
    result = await pipeline.get_pipeline_status()
    assert result["deskmanager"] == result["glpi"]
    assert result["deskmanager"]["detail"] == "TimeoutError"


@pytest.mark.asyncio
async def test_cancelled_glpi_probe_closes_acquired_session(monkeypatch):
    client = GLPIClient(
        base_url="http://ninf-glpi/apirest.php", app_token="app", user_token="user"
    )
    reading = asyncio.Event()

    async def read():
        reading.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(client, "init_session", AsyncMock(return_value="session"))
    monkeypatch.setattr(client, "get_my_entities", read)
    close = AsyncMock(return_value=True)
    monkeypatch.setattr(client, "kill_session", close)
    task = asyncio.create_task(client.readiness_probe())
    await asyncio.wait_for(reading.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    close.assert_awaited_once()
