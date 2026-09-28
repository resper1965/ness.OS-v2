from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


class FakeSession:
    def __init__(self, fails=False):
        self.execute = AsyncMock(
            side_effect=ConnectionError("database-secret") if fails else None
        )

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
    "failed_dependency", (None, "database", "redis", "broker", "redis_negative")
)
def test_api_readiness_requires_database_and_redis(failed_dependency):
    session = FakeSession(fails=failed_dependency == "database")
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
    session.execute.assert_awaited_once()
    if failed_dependency != "database":
        redis.ping.assert_awaited_once()
        redis.aclose.assert_awaited_once()
    if failed_dependency not in ("database", "redis", "redis_negative"):
        broker.ping.assert_awaited_once()
        broker.aclose.assert_awaited_once()
