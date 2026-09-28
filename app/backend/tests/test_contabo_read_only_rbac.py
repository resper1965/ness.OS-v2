from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.routers import contabo, contabo_mgmt
from app.core.dependencies import require_platform_admin
from app.main import app
from app.models.users import UserRole


def test_contabo_router_is_platform_admin_only_and_read_only():
    assert contabo.router.dependencies[0].dependency is require_platform_admin
    methods = {method for route in contabo.router.routes for method in route.methods}
    assert methods <= {"GET", "HEAD"}


def test_mutable_contabo_management_router_is_not_mounted():
    contabo_routes = [
        route
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/contabo")
    ]
    assert contabo_routes
    assert {
        method
        for route in contabo_routes
        for method in getattr(route, "methods", set())
    } <= {"GET", "HEAD"}
    assert not any(
        marker in route.path
        for route in contabo_routes
        for marker in ("block-ip", "open-port", "restart", "stop")
    )


def test_platform_admin_dependency_rejects_other_roles():
    with pytest.raises(HTTPException) as error:
        require_platform_admin(SimpleNamespace(role=UserRole.admin))
    assert error.value.status_code == 403


def test_platform_admin_dependency_accepts_platform_admin():
    user = SimpleNamespace(role=UserRole.platform_admin)
    assert require_platform_admin(user) is user


def test_dashboard_does_not_fetch_or_return_secrets():
    paths: list[str] = []

    class Client:
        def get(self, path: str):
            paths.append(path)
            return {"data": []}

    payload = contabo.get_dashboard_full(Client())
    assert "secrets" not in payload
    assert "/secrets" not in paths


@pytest.mark.parametrize(
    "operation",
    (
        lambda client: contabo.list_instances(client),
        lambda client: contabo.get_cloud_summary(client),
        lambda client: contabo.get_dashboard_full(client),
    ),
)
def test_contabo_failures_do_not_expose_provider_error(operation):
    class FailingClient:
        def get(self, _: str):
            raise RuntimeError("Bearer provider-secret")

    with pytest.raises(HTTPException) as error:
        operation(FailingClient())

    assert error.value.status_code == 502
    assert error.value.detail == "Contabo API indisponível."


@pytest.mark.asyncio
async def test_unmounted_contabo_management_route_hides_provider_error(monkeypatch):
    client = SimpleNamespace(
        list_firewalls=AsyncMock(side_effect=RuntimeError("Bearer provider-secret"))
    )
    monkeypatch.setattr(contabo_mgmt, "ContaboFirewallClient", lambda _: client)

    with pytest.raises(HTTPException) as error:
        await contabo_mgmt.list_firewalls()

    assert error.value.status_code == 502
    assert error.value.detail == "Contabo API indisponível."
    assert "provider-secret" not in str(error.value.detail)
