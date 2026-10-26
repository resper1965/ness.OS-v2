from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.routers import tenants as tenants_router_module
from app.api.routers.secops import router as secops_router
from app.api.routers.tenants import router as tenants_router
from app.core.dependencies import get_current_user, resolve_tenant_scope
from app.database import get_db
from app.models.users import UserRole


class _EmptyScalars:
    def all(self) -> list[object]:
        return []


class _EmptyResult:
    def scalars(self) -> _EmptyScalars:
        return _EmptyScalars()


class _FakeSession:
    statement: object | None = None

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, statement: object) -> _EmptyResult:
        self.statement = statement
        return _EmptyResult()


class _FailingSession(_FakeSession):
    async def execute(self, statement: object) -> _EmptyResult:
        raise RuntimeError("database password=private")


def _client(
    router,
    role: UserRole | None = None,
    tenant_id: str | None = None,
) -> tuple[FastAPI, TestClient]:
    app = FastAPI()
    app.include_router(router)
    if role is not None:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            role=role,
            tenant_id=tenant_id,
        )
    return app, TestClient(app)


@pytest.mark.parametrize(
    "path",
    (
        "/health",
        "/security-audit",
        "/list",
        "/tenant-a/summary",
    ),
)
def test_tenant_endpoints_require_authentication(path):
    _, client = _client(tenants_router)

    assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "json"),
    (
        ("get", "/api/secops/cve-intel", None),
        ("get", "/api/secops/zabbix-health", None),
        ("get", "/api/secops/triage-stats", None),
        ("post", "/api/secops/triage", {}),
        ("get", "/api/secops/decisions", None),
    ),
)
def test_secops_endpoints_require_authentication(method, path, json):
    _, client = _client(secops_router)

    assert client.request(method, path, json=json).status_code == 401


@pytest.mark.parametrize("path", ("/health", "/security-audit", "/list"))
def test_global_tenant_endpoints_reject_client_role(path):
    _, client = _client(tenants_router, UserRole.cliente, "tenant-a")

    assert client.get(path).status_code == 403


@pytest.mark.parametrize(
    ("method", "path", "json"),
    (
        ("get", "/api/secops/cve-intel", None),
        ("get", "/api/secops/zabbix-health", None),
        ("get", "/api/secops/triage-stats", None),
        ("post", "/api/secops/triage", {}),
    ),
)
def test_global_secops_endpoints_reject_client_role(method, path, json):
    _, client = _client(secops_router, UserRole.cliente, "tenant-a")

    assert client.request(method, path, json=json).status_code == 403


def test_client_cannot_read_another_tenant_summary():
    _, client = _client(tenants_router, UserRole.cliente, "tenant-a")

    assert client.get("/tenant-b/summary").status_code == 403


def test_client_can_read_own_tenant_summary():
    _, client = _client(tenants_router, UserRole.cliente, "tenant-a")

    with patch("app.api.routers.tenants.SessionLocal", return_value=_FakeSession()):
        response = client.get("/tenant-a/summary")

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "tenant-a",
        "assets_count": 0,
        "status": "active",
    }


def test_client_decisions_are_forced_to_own_tenant():
    app, client = _client(secops_router, UserRole.cliente, "tenant-a")
    session = _FakeSession()
    app.dependency_overrides[get_db] = lambda: session

    response = client.get("/api/secops/decisions")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert session.statement is not None
    assert "tenant-a" in session.statement.compile().params.values()


def test_client_cannot_request_decisions_from_another_tenant():
    _, client = _client(secops_router, UserRole.cliente, "tenant-a")

    assert client.get("/api/secops/decisions?customer_id=tenant-b").status_code == 403


def test_user_without_tenant_is_denied_tenant_scoped_access():
    user = SimpleNamespace(role=UserRole.cliente, tenant_id=None)

    with pytest.raises(HTTPException) as error:
        resolve_tenant_scope(user, None)

    assert getattr(error.value, "status_code", None) == 403


def test_operator_may_request_an_explicit_tenant_scope():
    user = SimpleNamespace(role=UserRole.soc, tenant_id=None)

    assert resolve_tenant_scope(user, "tenant-b") == "tenant-b"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    (
        lambda: tenants_router_module.list_tenants(),
        lambda: tenants_router_module.get_tenant_summary(
            "tenant-a", SimpleNamespace(role=UserRole.cliente, tenant_id="tenant-a")
        ),
    ),
)
async def test_tenant_database_errors_hide_details(monkeypatch, operation):
    monkeypatch.setattr(
        tenants_router_module, "SessionLocal", lambda: _FailingSession()
    )

    with pytest.raises(HTTPException) as error:
        await operation()

    assert getattr(error.value, "status_code", None) == 500
    assert getattr(error.value, "detail", None) == "Dados de tenants indisponíveis."
    assert "private" not in str(error.value)
