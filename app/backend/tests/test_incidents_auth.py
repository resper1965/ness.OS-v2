from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.incidents import router
from app.core.dependencies import get_current_user
from app.models.users import UserRole


class _EmptyScalars:
    def all(self) -> list[object]:
        return []


class _EmptyResult:
    def scalars(self) -> _EmptyScalars:
        return _EmptyScalars()


class _FakeSession:
    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, _: object) -> _EmptyResult:
        return _EmptyResult()


def _client(role: UserRole | None = None) -> tuple[FastAPI, TestClient]:
    app = FastAPI()
    app.include_router(router)
    if role is not None:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            role=role, tenant_id=None
        )
    return app, TestClient(app)


@pytest.mark.parametrize(
    ("method", "path", "json"),
    (
        ("get", "/api/incidents", None),
        ("post", "/api/incident/analyze", {"incident_data": {}}),
    ),
)
def test_incident_operations_require_authentication(method, path, json):
    _, client = _client()

    response = client.request(method, path, json=json)

    assert response.status_code == 401


@pytest.mark.parametrize("role", (UserRole.cliente, UserRole.helpdesk, UserRole.gestao))
@pytest.mark.parametrize(
    ("method", "path", "json"),
    (
        ("get", "/api/incidents", None),
        ("post", "/api/incident/analyze", {"incident_data": {}}),
    ),
)
def test_incident_operations_reject_non_operator_roles(role, method, path, json):
    _, client = _client(role)

    response = client.request(method, path, json=json)

    assert response.status_code == 403


@pytest.mark.parametrize(
    "role",
    (UserRole.noc, UserRole.soc, UserRole.admin, UserRole.platform_admin),
)
def test_incident_list_allows_operator_roles(role):
    _, client = _client(role)

    with patch("app.api.routers.incidents.SessionLocal", return_value=_FakeSession()):
        response = client.get("/api/incidents")

    assert response.status_code == 200
    assert response.json() == {"incidents": [], "total": 0}


def test_incident_analysis_queues_work_for_noc():
    _, client = _client(UserRole.noc)

    with patch(
        "app.workers.postmortem.generate_postmortem_report.apply_async"
    ) as apply_async:
        response = client.post(
            "/api/incident/analyze",
            json={"incident_data": {"fingerprint": "fp-1"}, "ticket_id": "GLPI-1"},
        )

    assert response.status_code == 202
    apply_async.assert_called_once_with(
        args=[{"fingerprint": "fp-1"}, "GLPI-1"],
        queue="ml",
    )


@pytest.mark.parametrize(
    "active_user",
    (
        None,
        SimpleNamespace(id=1, role=UserRole.soc, tenant_id="tenant-a"),
        SimpleNamespace(id=1, role=UserRole.noc, tenant_id="tenant-b"),
    ),
    ids=("revoked", "role-changed", "tenant-changed"),
)
def test_incident_stream_emits_auth_event_when_identity_changes(active_user):
    class _PubSub:
        async def subscribe(self, _: str) -> None:
            return None

        async def get_message(self, **_: object) -> None:
            return None

        async def unsubscribe(self, _: str) -> None:
            return None

        async def close(self) -> None:
            return None

    class _Redis:
        def pubsub(self) -> _PubSub:
            return _PubSub()

        async def aclose(self) -> None:
            return None

    app, client = _client(UserRole.noc)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, role=UserRole.noc, tenant_id="tenant-a"
    )
    with (
        patch("app.api.routers.incidents.Redis.from_url", return_value=_Redis()),
        patch("app.api.routers.incidents.get_settings", return_value=SimpleNamespace(redis_url="redis://")),
        patch(
            "app.api.routers.incidents._load_stream_user",
            new=AsyncMock(return_value=active_user),
        ),
    ):
        response = client.get("/api/incidents/stream", headers={"Authorization": "Bearer test"})

    assert response.status_code == 200
    assert 'event: auth\ndata: {"reason":"session_invalid"}' in response.text
