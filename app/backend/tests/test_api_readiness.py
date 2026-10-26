from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


class FakeSession:
    def __init__(self, fails=False, missing_schema=False):
        if fails:
            side_effect = ConnectionError("database-secret")
        elif missing_schema:
            side_effect = [None, RuntimeError("missing-schema"), None]
        else:
            side_effect = None
        self.execute = AsyncMock(side_effect=side_effect)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


class FakeRedis:
    def __init__(self, fails=False, returns=True):
        self.ping = AsyncMock(
            side_effect=ConnectionError("redis-secret") if fails else None,
            return_value=returns,
        )
        self.aclose = AsyncMock()


@pytest.mark.parametrize(
    "failed_dependency",
    (None, "database", "schema", "redis", "broker", "redis_negative"),
)
def test_api_readiness_requires_database_and_redis(failed_dependency):
    session = FakeSession(
        fails=failed_dependency == "database",
        missing_schema=failed_dependency == "schema",
    )
    redis = FakeRedis(
        fails=failed_dependency == "redis",
        returns=failed_dependency != "redis_negative",
    )
    broker = FakeRedis(fails=failed_dependency == "broker")
    clients = [redis, broker]
    with (
        patch("app.main.SessionLocal", return_value=session),
        patch("app.main.Redis.from_url", side_effect=clients),
        TestClient(app) as client,
    ):
        response = client.get("/ready")

    assert response.status_code == (503 if failed_dependency else 200)
    assert response.json() == (
        {"detail": "unavailable"} if failed_dependency else {"status": "ready"}
    )
    assert "secret" not in response.text
    assert session.execute.await_count == {"database": 1, "schema": 2}.get(
        failed_dependency, 3
    )
    if failed_dependency not in ("database", "schema"):
        redis.ping.assert_awaited_once()
        redis.aclose.assert_awaited_once()
    if failed_dependency not in ("database", "schema", "redis", "redis_negative"):
        broker.ping.assert_awaited_once()
        broker.aclose.assert_awaited_once()
