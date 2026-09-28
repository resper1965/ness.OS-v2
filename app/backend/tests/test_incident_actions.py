from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.incidents import router
from app.core.dependencies import get_current_user
from app.models.users import UserRole


class FakeSession:
    def __init__(self, incident):
        self.incident = incident
        self.actions = []
        self.statement = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    @asynccontextmanager
    async def begin(self):
        yield

    async def execute(self, statement):
        self.statement = statement
        return SimpleNamespace(scalar_one_or_none=lambda: self.incident)

    def add(self, action):
        self.actions.append(action)


def _client(role=UserRole.noc, tenant_id=None):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=42, role=role, tenant_id=tenant_id
    )
    return TestClient(app)


def _incident(status="open", ticket_id=None, tags=None):
    return SimpleNamespace(
        id=7,
        status=status,
        assigned_user_id=None,
        deskmanager_ticket_id=ticket_id,
        tags=tags or {"ninf_customer_name": "tenant-a"},
    )


def test_acknowledge_is_atomic_and_attributed():
    incident = _incident()
    session = FakeSession(incident)
    with patch("app.api.routers.incidents.SessionLocal", return_value=session):
        response = _client().post(
            "/api/incidents/7/actions", json={"action": "acknowledge"}
        )

    assert response.status_code == 200
    assert response.json()["status"] == "acknowledged"
    assert incident.status == "acknowledged"
    assert len(session.actions) == 1
    assert session.actions[0].actor_user_id == 42
    assert session.actions[0].action == "acknowledge"
    assert session.actions[0].previous_status == "open"
    assert session.statement._for_update_arg is not None


def test_assign_self_and_comment_record_actor():
    incident = _incident()
    session = FakeSession(incident)
    with patch("app.api.routers.incidents.SessionLocal", return_value=session):
        assign = _client().post(
            "/api/incidents/7/actions", json={"action": "assign_self"}
        )
        comment = _client().post(
            "/api/incidents/7/actions",
            json={"action": "comment", "note": "Investigando CPU"},
        )

    assert assign.status_code == comment.status_code == 200
    assert incident.assigned_user_id == 42
    assert [a.action for a in session.actions] == ["assign_self", "comment"]
    assert session.actions[1].note == "Investigando CPU"


@pytest.mark.parametrize(
    ("action", "status", "ticket_id", "tags"),
    (
        ("resolve", "open", "404", {}),
        ("close", "open", None, {}),
        ("acknowledge", "resolved", None, {}),
    ),
)
def test_invalid_transition_does_not_write_audit(action, status, ticket_id, tags):
    incident = _incident(status, ticket_id, tags)
    session = FakeSession(incident)
    with patch("app.api.routers.incidents.SessionLocal", return_value=session):
        response = _client().post(
            "/api/incidents/7/actions", json={"action": action, "note": "Motivo"}
        )
    assert response.status_code == 409
    assert session.actions == []


def test_tenant_user_cannot_mutate_incident():
    response = _client(UserRole.cliente).post(
        "/api/incidents/7/actions", json={"action": "acknowledge"}
    )
    assert response.status_code == 403


def test_scoped_operator_can_act_only_on_own_incident():
    own = FakeSession(_incident(tags={"ninf_customer_name": "tenant-a"}))
    with patch("app.api.routers.incidents.SessionLocal", return_value=own):
        allowed = _client(UserRole.operator, "tenant-a").post(
            "/api/incidents/7/actions", json={"action": "acknowledge"}
        )
    assert allowed.status_code == 200
    assert len(own.actions) == 1
    assert own.statement.compile().params["tags_1"] == "ninf_customer_name"

    other = FakeSession(_incident(tags={"ninf_customer_name": "tenant-b"}))
    with patch("app.api.routers.incidents.SessionLocal", return_value=other):
        denied = _client(UserRole.operator, "tenant-a").post(
            "/api/incidents/7/actions", json={"action": "acknowledge"}
        )
    assert denied.status_code == 404
    assert other.actions == []


def test_viewer_cannot_mutate_incident():
    response = _client(UserRole.viewer, "tenant-a").post(
        "/api/incidents/7/actions", json={"action": "acknowledge"}
    )
    assert response.status_code == 403


def test_missing_incident_and_empty_comment_are_rejected():
    session = FakeSession(None)
    with patch("app.api.routers.incidents.SessionLocal", return_value=session):
        missing = _client().post(
            "/api/incidents/7/actions", json={"action": "acknowledge"}
        )
    empty = _client().post(
        "/api/incidents/7/actions", json={"action": "comment", "note": "  "}
    )
    assert missing.status_code == 404
    assert empty.status_code == 422
