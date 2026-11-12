from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import dashboard
from app.core.dependencies import get_current_user
from app.dependencies import get_redis
from app.models.users import UserRole


class FakeRedis:
    async def get(self, _):
        return None

    async def set(self, _, __):
        return None


async def _fake_redis_dep():
    yield FakeRedis()


def _client() -> tuple[FastAPI, TestClient]:
    app = FastAPI()
    app.include_router(dashboard.router)
    app.dependency_overrides[get_redis] = _fake_redis_dep
    return app, TestClient(app)


def test_stack_health_requires_authentication():
    _, client = _client()
    assert client.get("/api/ops/stack-health").status_code == 401


def test_stack_health_rejects_client_role():
    app, client = _client()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role=UserRole.cliente
    )
    assert client.get("/api/ops/stack-health").status_code == 403


def test_stack_health_returns_consolidated_payload(monkeypatch):
    app, client = _client()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.noc)

    async def fake_sources(_):
        return {
            "zabbix": {"status": "ok"},
            "glpi": {"status": "ok"},
        }

    async def fake_contabo():
        return {
            "status": "ok",
            "stacks": {
                "aiops": {"status": "ok", "provider_status": "running"},
                "zabbix-prod": {"status": "ok", "provider_status": "running"},
                "zabbix-prd-01": {"status": "ok", "provider_status": "running"},
            },
        }

    async def fake_pipeline():
        return {"status": "ok", "checked_at": "2026-11-12T12:00:00+00:00"}

    monkeypatch.setattr(dashboard, "_collect_sources", fake_sources)
    monkeypatch.setattr(dashboard, "_collect_contabo_stacks", fake_contabo)
    monkeypatch.setattr(dashboard, "pipeline_health", fake_pipeline)

    response = client.get("/api/ops/stack-health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {"total": 3, "ok": 3, "degraded": 0, "down": 0}
    assert payload["findings"] == []
