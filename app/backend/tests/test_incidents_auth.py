import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.routers.incidents import router, stream_incidents
from app.core.dependencies import get_current_user
from app.core.jwt import create_access_token
from app.models.users import UserRole


class _EmptyScalars:
    def all(self) -> list[object]:
        return []


class _EmptyResult:
    def scalars(self) -> _EmptyScalars:
        return _EmptyScalars()


class _FakeSession:
    statement = None

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, statement: object) -> _EmptyResult:
        self.statement = statement
        return _EmptyResult()


def _client(
    role: UserRole | None = None, tenant_id: str | None = None
) -> tuple[FastAPI, TestClient]:
    app = FastAPI()
    app.include_router(router)
    if role is not None:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            role=role, tenant_id=tenant_id
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


@pytest.mark.parametrize("role", (UserRole.operator, UserRole.viewer))
def test_scoped_roles_list_only_their_tenant(role):
    _, client = _client(role, "tenant-a")
    session = _FakeSession()
    with patch("app.api.routers.incidents.SessionLocal", return_value=session):
        response = client.get("/api/incidents")
        denied = client.get("/api/incidents?tenant_id=tenant-b")

    assert response.status_code == 200
    assert session.statement.compile().params["tags_1"] == "ninf_customer_name"
    assert denied.status_code == 403


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


class _StreamPubsub:
    def __init__(self, tenants=("tenant-a",)):
        self.tenants = iter(tenants)

    async def subscribe(self, _: str) -> None:
        pass

    async def get_message(self, **_: object) -> dict[str, str]:
        return {
            "data": json.dumps(
                {"tenant_id": next(self.tenants, "tenant-a"), "id": "inc-1"}
            )
        }

    async def unsubscribe(self, _: str) -> None:
        pass

    async def close(self) -> None:
        pass


class _StreamRedis:
    def __init__(self, tenants=("tenant-a",)):
        self.tenants = tenants

    def pubsub(self) -> _StreamPubsub:
        return _StreamPubsub(self.tenants)

    async def aclose(self) -> None:
        pass


class _StreamSession:
    def __init__(self, user: SimpleNamespace) -> None:
        self.user = user

    async def __aenter__(self) -> "_StreamSession":
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def execute(self, _: object) -> SimpleNamespace:
        return SimpleNamespace(scalar_one_or_none=lambda: self.user)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", (UserRole.cliente, UserRole.operator, UserRole.viewer))
async def test_stream_delivers_event_while_session_is_current(role):
    user = SimpleNamespace(id=42, role=role, tenant_id="tenant-a", is_active=True)
    token = create_access_token(
        user_id=42,
        role=role.value,
        extra_claims={"tenant_id": "tenant-a"},
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/incidents/stream",
            "headers": [(b"cookie", f"ninf_session={token}".encode())],
        }
    )
    with (
        patch("app.api.routers.incidents.Redis.from_url", return_value=_StreamRedis()),
        patch(
            "app.api.routers.incidents.SessionLocal",
            return_value=_StreamSession(user),
        ),
    ):
        response = await stream_incidents(request=request, current_user=user)
        events = response.body_iterator
        assert (await anext(events)).startswith("event: ping")
        assert '"id": "inc-1"' in await anext(events)
        await events.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", (UserRole.operator, UserRole.viewer))
async def test_scoped_stream_skips_another_tenant(role):
    user = SimpleNamespace(id=42, role=role, tenant_id="tenant-a", is_active=True)
    token = create_access_token(
        user_id=42,
        role=role.value,
        extra_claims={"tenant_id": "tenant-a"},
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/incidents/stream",
            "headers": [(b"cookie", f"ninf_session={token}".encode())],
        }
    )
    with (
        patch(
            "app.api.routers.incidents.Redis.from_url",
            return_value=_StreamRedis(("tenant-b", "tenant-a")),
        ),
        patch(
            "app.api.routers.incidents.SessionLocal",
            return_value=_StreamSession(user),
        ),
    ):
        response = await stream_incidents(request=request, current_user=user)
        events = response.body_iterator
        assert (await anext(events)).startswith("event: ping")
        delivered = await anext(events)
        assert '"tenant_id": "tenant-a"' in delivered
        assert '"tenant_id": "tenant-b"' not in delivered
        await events.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ("is_active", "role", "tenant_id", "session_epoch"))
async def test_stream_closes_before_delivering_event_after_identity_change(changed):
    user = SimpleNamespace(
        id=42, role=UserRole.cliente, tenant_id="tenant-a", is_active=True
    )
    token = create_access_token(
        user_id=42,
        role=UserRole.cliente.value,
        extra_claims={"tenant_id": "tenant-a"},
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/incidents/stream",
            "headers": [(b"cookie", f"ninf_session={token}".encode())],
        }
    )
    with (
        patch("app.api.routers.incidents.Redis.from_url", return_value=_StreamRedis()),
        patch(
            "app.api.routers.incidents.SessionLocal",
            return_value=_StreamSession(user),
        ),
    ):
        response = await stream_incidents(request=request, current_user=user)
        events = response.body_iterator
        assert (await anext(events)).startswith("event: ping")
        setattr(
            user,
            changed,
            {
                "is_active": False,
                "role": UserRole.noc,
                "tenant_id": "tenant-b",
                "session_epoch": 1,
            }[changed],
        )
        assert (await anext(events)).startswith("event: auth\n")
        await events.aclose()


@pytest.mark.asyncio
async def test_stream_closes_when_session_token_expires():
    user = SimpleNamespace(
        id=42, role=UserRole.cliente, tenant_id="tenant-a", is_active=True
    )
    token = create_access_token(
        user_id=42,
        role=UserRole.cliente.value,
        expire_hours=-1,
        extra_claims={"tenant_id": "tenant-a"},
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/incidents/stream",
            "headers": [(b"cookie", f"ninf_session={token}".encode())],
        }
    )
    with (
        patch("app.api.routers.incidents.Redis.from_url", return_value=_StreamRedis()),
        patch(
            "app.api.routers.incidents.SessionLocal",
            return_value=_StreamSession(user),
        ),
    ):
        response = await stream_incidents(request=request, current_user=user)
        events = response.body_iterator
        assert (await anext(events)).startswith("event: ping")
        assert (await anext(events)).startswith("event: auth\n")
        await events.aclose()
