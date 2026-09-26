from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.api.routers import incidents, pipeline
from app.core.dependencies import get_current_user
from app.integrations import pipeline_health as health
from app.integrations.cmdb_sync import exact_match, host_marker
from app.integrations.glpi import GLPIClient
from app.models import UserRole


def test_cmdb_identity_does_not_use_name_or_shared_ip():
    index = {"123": [{"id": 7, "entities_id": 8}]}
    assert exact_match(index, "123", 8)["id"] == 7
    assert exact_match(index, "123", 3) is None
    assert exact_match(index, "124", 8) is None
    index["123"].append({"id": 8, "entities_id": 8})
    assert exact_match(index, "123", 8) is None
    assert host_marker("Zabbix Host ID: 123\nIP: 10.0.0.1") == "123"


def test_client_incident_query_is_scoped_and_cannot_widen(monkeypatch):
    app = FastAPI()
    app.include_router(incidents.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role=UserRole.cliente, tenant_id="cavan"
    )
    session = AsyncMock()
    session.__aenter__.return_value = session
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    monkeypatch.setattr(incidents, "SessionLocal", lambda: session)
    with TestClient(app) as client:
        assert client.get("/api/incidents").status_code == 200
        sql = str(
            session.execute.call_args.args[0].compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        assert "lower" in sql and "'cavan'" in sql and "ninf_customer_name" in sql
        assert client.get("/api/incidents?tenant_id=alupar").status_code == 403


def test_pipeline_status_requires_operator():
    app = FastAPI()
    app.include_router(pipeline.router)
    with TestClient(app) as client:
        assert client.get("/api/dashboard/pipeline-status").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            role=UserRole.cliente, tenant_id="cavan"
        )
        assert client.get("/api/dashboard/pipeline-status").status_code == 403


@pytest.mark.asyncio
async def test_empty_queues_with_no_workers_are_not_healthy(monkeypatch):
    redis = AsyncMock()
    redis.llen.return_value = 0
    redis.hgetall.return_value = {}
    monkeypatch.setattr(health.Redis, "from_url", lambda *a, **kw: redis)
    inspector = MagicMock()
    inspector.active_queues.return_value = None
    monkeypatch.setattr(health.celery_app.control, "inspect", lambda **kw: inspector)
    result = await health.workers_health()
    assert result["status"] == "error"
    assert "alerts.primary" in result["missing_consumers"]


@pytest.mark.asyncio
async def test_exhausted_task_is_visible_even_with_live_workers(monkeypatch):
    redis = AsyncMock()
    redis.llen.return_value = 0
    redis.hgetall.return_value = {"x": '{"state":"failed"}'}
    monkeypatch.setattr(health.Redis, "from_url", lambda *a, **kw: redis)
    inspector = MagicMock()
    inspector.active_queues.return_value = {
        "worker": [{"name": q} for q in ("alerts.primary", "alerts.deferred", "ml")]
    }
    monkeypatch.setattr(health.celery_app.control, "inspect", lambda **kw: inspector)
    result = await health.workers_health()
    assert result["status"] == "error" and result["failed_tasks"] == 1


@pytest.mark.asyncio
async def test_ticket_cannot_link_other_client_asset():
    g = GLPIClient()
    g.session_token = "session"
    g.get_item = AsyncMock(return_value={"entities_id": 3})
    with pytest.raises(ValueError, match="same entity"):
        await g.create_ticket(
            "t", "c", entity_id=8, linked_item={"itemtype": "Computer", "id": 1}
        )
