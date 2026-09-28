from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from app.api.routers.auth import map_authentik_role
from app.core.dependencies import (
    require_admin,
    require_noc,
    require_operator,
    require_platform_admin,
    resolve_tenant_scope,
)
from app.main import app
from app.models.users import UserRole


@pytest.mark.parametrize("guard", (require_noc, require_admin, require_platform_admin))
def test_platform_admin_is_authorized_by_administrative_guards(guard):
    user = SimpleNamespace(role=UserRole.platform_admin)
    assert guard(user) is user


@pytest.mark.parametrize("role", (UserRole.cliente, UserRole.helpdesk, UserRole.gestao))
def test_non_admin_roles_are_rejected_by_admin_guard(role):
    with pytest.raises(HTTPException) as error:
        require_admin(SimpleNamespace(role=role))
    assert error.value.status_code == 403


def test_local_admin_is_not_platform_admin():
    with pytest.raises(HTTPException) as error:
        require_platform_admin(SimpleNamespace(role=UserRole.admin))
    assert error.value.status_code == 403


@pytest.mark.parametrize("group", ("platform_admin", "ness-os-platform-admin"))
def test_platform_admin_group_aliases_map_to_global_role(group):
    assert map_authentik_role({"groups": [group]}) == UserRole.platform_admin


def test_unknown_group_falls_back_to_least_privileged_role():
    assert map_authentik_role({"groups": ["unknown"]}) == UserRole.cliente


@pytest.mark.parametrize("group,role", (("operator", "operator"), ("viewer", "viewer")))
def test_scoped_authentik_groups_map_to_scoped_roles(group, role):
    assert map_authentik_role({"groups": [group]}).value == role


def test_scoped_group_wins_over_legacy_noc_group():
    assert map_authentik_role({"groups": ["noc", "operator"]}) == UserRole.operator
    assert map_authentik_role({"groups": ["noc", "viewer"]}) == UserRole.viewer


@pytest.mark.parametrize("role", ("operator", "viewer"))
def test_scoped_roles_cannot_select_another_tenant(role):
    user = SimpleNamespace(role=UserRole(role), tenant_id="tenant-a")
    assert resolve_tenant_scope(user, None) == "tenant-a"
    with pytest.raises(HTTPException) as error:
        resolve_tenant_scope(user, "tenant-b")
    assert error.value.status_code == 403


def test_operator_guard_allows_scoped_operator_but_not_viewer():
    operator = SimpleNamespace(role=UserRole.operator, tenant_id="tenant-a")
    assert require_operator(operator) is operator
    with pytest.raises(HTTPException) as error:
        require_operator(SimpleNamespace(role=UserRole.viewer, tenant_id="tenant-a"))
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        require_noc(operator)
    assert error.value.status_code == 403


def test_every_non_public_api_route_has_recognized_authorization():
    public = {
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/logout"),
        ("POST", "/api/auth/oidc/callback"),
        ("POST", "/api/auth/seed"),
        ("GET", "/api/v1/push/config"),
    }
    guards = {
        "get_current_user",
        "require_authenticated",
        "require_noc",
        "require_operator",
        "require_admin",
        "require_platform_admin",
        "verify_api_key",
        "verify_webhook_key",
    }
    missing = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith(
            ("/api/", "/v1/", "/webhook/")
        ):
            continue
        names = {
            getattr(dependency.call, "__name__", type(dependency.call).__name__)
            for dependency in route.dependant.dependencies
        }
        for method in route.methods:
            if (method, route.path) not in public and not names.intersection(guards):
                missing.append((method, route.path))
    assert missing == []
