import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.routers import dashboard, secops
from app.services.operational_status import observe_source


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value):
        self.values[key] = value


@pytest.mark.asyncio
async def test_success_then_failure_preserves_last_valid_collection():
    cache = FakeRedis()
    first = datetime(2026, 9, 28, 10, tzinfo=timezone.utc)

    async def healthy():
        return {"hosts_active": 5}

    async def failed():
        raise TimeoutError("token and endpoint must not leak")

    success = await observe_source("zabbix", healthy, cache, now=first)
    failure = await observe_source(
        "zabbix", failed, cache, now=first + timedelta(minutes=3)
    )

    assert success.status == "ok"
    assert success.last_success_at == first
    assert success.stale is False
    assert failure.status == "degraded"
    assert failure.data == {"hosts_active": 5}
    assert failure.last_success_at == first
    assert failure.observed_at == first + timedelta(minutes=3)
    assert failure.freshness_seconds == 180
    assert failure.stale is True
    assert failure.error_code == "TimeoutError"
    assert "token" not in failure.model_dump_json()


@pytest.mark.asyncio
async def test_failure_without_last_value_is_down():
    async def failed():
        raise RuntimeError("secret")

    result = await observe_source("glpi", failed, FakeRedis())

    assert result.status == "down"
    assert result.data is None
    assert result.last_success_at is None
    assert result.error_code == "RuntimeError"


@pytest.mark.asyncio
async def test_collector_deadline_is_reported_as_timeout():
    async def slow():
        await asyncio.sleep(1)
        return {"hosts_active": 5}

    result = await observe_source("zabbix", slow, FakeRedis(), timeout_seconds=0.001)

    assert result.status == "down"
    assert result.error_code == "TimeoutError"


@pytest.mark.asyncio
async def test_unconfigured_source_does_not_call_collector():
    called = False

    async def collector():
        nonlocal called
        called = True

    result = await observe_source("atera", collector, FakeRedis(), configured=False)

    assert result.status == "unavailable"
    assert result.error_code == "not_configured"
    assert result.data is None
    assert called is False


@pytest.mark.asyncio
async def test_dashboard_sources_keep_source_failures_separate(monkeypatch):
    monkeypatch.setattr(
        dashboard,
        "get_settings",
        lambda: SimpleNamespace(
            zabbix_api_token="token",
            atera_api_key="",
            glpi_app_token="app",
            glpi_user_token="user",
        ),
    )
    monkeypatch.setattr(
        dashboard,
        "_zabbix_summary",
        AsyncMock(return_value={"hosts_active": 5}),
    )
    glpi = SimpleNamespace(
        readiness_probe=AsyncMock(side_effect=RuntimeError("secret"))
    )
    monkeypatch.setattr(dashboard, "GLPIClient", lambda: glpi)

    result = await dashboard.get_operational_sources(FakeRedis())
    sources = result["sources"]

    assert sources["zabbix"]["status"] == "ok"
    assert sources["zabbix"]["data"] == {"hosts_active": 5}
    assert sources["atera"]["status"] == "unavailable"
    assert sources["glpi"]["status"] == "down"
    assert sources["glpi"]["error_code"] == "RuntimeError"
    assert sources["wazuh"]["status"] == "planned"
    assert "secret" not in str(result)


@pytest.mark.asyncio
async def test_secops_zabbix_failure_does_not_publish_secret_or_score(monkeypatch):
    monkeypatch.setattr(
        secops, "_zabbix", AsyncMock(side_effect=RuntimeError("private token"))
    )

    result = await secops.zabbix_health()

    assert result["overall"] == "unknown"
    assert result["checks"] == []
    assert result["error"] == "RuntimeError"
    assert "private token" not in str(result)
