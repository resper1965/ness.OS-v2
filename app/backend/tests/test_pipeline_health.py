import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.routers import pipeline
from app.integrations import pipeline_health as health
from app.integrations.glpi import GLPIClient
from app.workers.celery_app import add_publish_timestamp


class FakeCache:
    def __init__(self, saved=None):
        self.saved = dict(saved or {})

    async def set(self, key, value):
        self.saved[key] = value

    async def get(self, key):
        return self.saved.get(key)

    async def aclose(self):
        pass


@pytest.fixture(autouse=True)
def cache(monkeypatch):
    fake = FakeCache()
    monkeypatch.setattr(health.Redis, "from_url", lambda *a, **kw: fake)
    return fake


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
@pytest.mark.parametrize(
    (
        "depth",
        "active_queues",
        "redis_error",
        "published_age_seconds",
        "expected_status",
    ),
    [
        (0, ("alerts.primary", "alerts.deferred", "ml"), False, None, "ok"),
        (1, ("alerts.primary", "alerts.deferred", "ml"), False, 30, "ok"),
        (101, ("alerts.primary", "alerts.deferred", "ml"), False, 600, "degraded"),
        (1, ("alerts.primary", "alerts.deferred", "ml"), False, None, "degraded"),
        (0, ("alerts.primary", "alerts.deferred"), False, None, "error"),
        (0, ("alerts.primary", "alerts.deferred", "ml"), True, None, "error"),
    ],
)
async def test_workers_health_uses_celery_broker_for_queue_depth(
    monkeypatch,
    depth,
    active_queues,
    redis_error,
    published_age_seconds,
    expected_status,
):
    broker_url = "redis://:broker-password@broker.internal:6379/1"
    telemetry_url = "redis://redis.internal:6379/0"
    broker_connection = Mock()
    broker_connection.as_uri.return_value = broker_url
    broker_connection.release = Mock()

    class FakeRedis:
        def __init__(self, url):
            self.url = url
            self.closed = False

        async def llen(self, queue):
            if redis_error:
                raise ConnectionError("redis unavailable")
            return depth if queue == "alerts.primary" else 0

        async def lindex(self, queue, _index):
            if queue != "alerts.primary" or not depth:
                return None
            headers = {}
            if published_age_seconds is not None:
                headers["ninf_published_at"] = time.time() - published_age_seconds
            return json.dumps({"headers": headers})

        async def hgetall(self, _key):
            return {}

        async def aclose(self):
            self.closed = True

    clients = []

    def make_redis(url, **_kwargs):
        client = FakeRedis(url)
        clients.append(client)
        return client

    inspection = SimpleNamespace(
        active_queues=Mock(
            return_value={"worker@node": [{"name": queue} for queue in active_queues]}
        )
    )
    celery = SimpleNamespace(
        connection_for_read=Mock(return_value=broker_connection),
        control=SimpleNamespace(inspect=Mock(return_value=inspection)),
    )
    monkeypatch.setattr(health, "celery_app", celery)
    monkeypatch.setattr(health, "Redis", SimpleNamespace(from_url=make_redis))
    monkeypatch.setattr(
        health, "get_settings", lambda: SimpleNamespace(redis_url=telemetry_url)
    )

    result = await health.workers_health()

    assert [client.url for client in clients] == [broker_url, telemetry_url]
    assert result["status"] == expected_status
    assert "broker-password" not in str(result)
    if redis_error:
        assert result["error"] == "ConnectionError"
    else:
        assert result["redis_db"] == 1
        assert result["queue_health"][0]["queue"] == "alerts.primary"
        assert result["queue_health"][0]["depth"] == depth
        if "ml" not in active_queues:
            assert result["queue_health"][-1]["status"] == "error"
        else:
            assert result["queue_health"][0]["status"] == expected_status
        age = result["queue_health"][0]["oldest_age_seconds"]
        if depth and published_age_seconds is not None:
            assert abs(age - published_age_seconds) <= 2
        elif not depth:
            assert age == 0
        else:
            assert age is None
    assert all(client.closed for client in clients)
    broker_connection.as_uri.assert_called_once_with(include_password=True)
    broker_connection.release.assert_called_once_with()


def test_before_publish_adds_timestamp_to_task_headers():
    headers = {"task": "app.workers.tasks.process_alert"}
    before = time.time()

    add_publish_timestamp(headers=headers)

    assert before <= headers["ninf_published_at"] <= time.time()
    assert headers["task"] == "app.workers.tasks.process_alert"


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


def _probes(monkeypatch, zabbix):
    monkeypatch.setattr(health.ZabbixClient, "readiness_probe", AsyncMock(**zabbix))
    monkeypatch.setattr(
        health.GLPIClient,
        "readiness_probe",
        AsyncMock(return_value={"status": "ready"}),
    )
    ok = AsyncMock(return_value={"status": "ok"})
    monkeypatch.setattr(health, "workers_health", ok)
    monkeypatch.setattr(health, "incident_health", ok)


@pytest.mark.asyncio
async def test_stopped_source_makes_pipeline_not_ready(monkeypatch, cache):
    old = datetime.now(timezone.utc) - timedelta(
        seconds=health.MAX_SOURCE_AGE_SECONDS + 60
    )
    cache.saved["ninf:pipeline:last-success:zabbix"] = old.isoformat()
    _probes(monkeypatch, {"side_effect": TimeoutError("secret-token")})
    result = await health.pipeline_health()
    zabbix = result["zabbix"]
    assert result["ready"] is False and result["status"] == "degraded"
    assert zabbix["stale"] is True and zabbix["last_error"] == "TimeoutError"
    assert "secret-token" not in str(result)
    assert zabbix["last_success_at"] == old.isoformat()
    assert zabbix["freshness_seconds"] > health.MAX_SOURCE_AGE_SECONDS
    assert zabbix["scope"] == "global"
    assert result["glpi"]["stale"] is False and result["glpi"]["freshness_seconds"] == 0


@pytest.mark.asyncio
async def test_recent_failure_and_never_succeeded(monkeypatch, cache):
    recent = datetime.now(timezone.utc) - timedelta(seconds=30)
    cache.saved["ninf:pipeline:last-success:zabbix"] = recent.isoformat()
    _probes(monkeypatch, {"side_effect": TimeoutError("secret-token")})
    result = await health.pipeline_health()
    assert result["ready"] is True and result["status"] == "degraded"
    assert result["zabbix"]["stale"] is False

    cache.saved.clear()
    result = await health.pipeline_health()
    assert result["ready"] is False
    assert result["zabbix"]["last_success_at"] is None
    assert result["zabbix"]["freshness_seconds"] is None
