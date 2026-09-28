from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.incidents import router
from app.core.dependencies import get_current_user
from app.models.users import UserRole


class FakeSession:
    def __init__(self, incident, actions=()):
        self.incident = incident
        self.actions = actions
        self.statement = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def execute(self, statement):
        if self.statement is None:
            self.statement = statement
            return SimpleNamespace(scalar_one_or_none=lambda: self.incident)
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: self.actions)
        )


def _client(role=UserRole.cliente, tenant_id="tenant-a"):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, role=role, tenant_id=tenant_id
    )
    return TestClient(app)


def _incident(tenant="tenant-a"):
    when = datetime(2026, 9, 28, 10, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=7,
        fingerprint="fingerprint",
        title="CPU elevada",
        severity=4,
        status="open",
        assigned_user_id=None,
        host_id="101",
        host_name="host-a",
        trigger_id="202",
        asset_id=None,
        asset=None,
        alert_count=2,
        first_seen=when,
        last_seen=when,
        sanitized_description="Descrição segura",
        tags={
            "ninf_customer_name": tenant,
            "ninf_zabbix_event_id": "303",
            "ninf_zabbix_status": "resolved",
            "ninf_zabbix_recovered_at": "2026-09-28T11:00:00+00:00",
            "resolution_sync_status": "pending",
        },
        deskmanager_ticket_id="404",
    )


def test_detail_exposes_source_and_ticket_in_authorized_tenant():
    action = SimpleNamespace(
        id=1,
        actor_user_id=42,
        actor_source="user",
        action="acknowledge",
        previous_status="open",
        new_status="acknowledged",
        previous_assignee_id=None,
        new_assignee_id=None,
        note=None,
        created_at=datetime(2026, 9, 28, 11, tzinfo=timezone.utc),
    )
    session = FakeSession(_incident(), [action])
    with patch("app.api.routers.incidents.SessionLocal", return_value=session):
        response = _client().get("/api/incidents/7")

    assert response.status_code == 200
    assert response.json()["source_event_id"] == "303"
    assert response.json()["source_status"] == "resolved"
    assert response.json()["source_recovered_at"] == "2026-09-28T11:00:00+00:00"
    assert response.json()["source_url"].endswith(
        "/tr_events.php?triggerid=202&eventid=303"
    )
    assert response.json()["trigger_id"] == "202"
    assert response.json()["description"] == "Descrição segura"
    assert response.json()["ticket_id"] == "404"
    assert response.json()["resolution_sync_status"] == "pending"
    assert response.json()["actions"][0]["actor_user_id"] == 42
    params = session.statement.compile().params
    assert params["tags_1"] == "ninf_customer_name"
    assert params["lower_1"] == "tenant-a"


@pytest.mark.parametrize("incident", (None, _incident("tenant-b")))
def test_detail_hides_missing_or_cross_tenant_incident(incident):
    session = FakeSession(incident)
    with patch("app.api.routers.incidents.SessionLocal", return_value=session):
        response = _client().get("/api/incidents/7")

    assert response.status_code == 404


def test_detail_requires_authentication():
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/api/incidents/7")
    assert response.status_code == 401
