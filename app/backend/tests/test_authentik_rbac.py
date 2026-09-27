from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routers.auth import map_authentik_role, normalize_authentik_identity
from app.core.dependencies import (
    get_current_user,
    require_admin,
    require_noc,
    require_platform_admin,
)
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


@pytest.mark.parametrize(
    ("group", "expected"),
    (("operator", UserRole.helpdesk), ("viewer", UserRole.cliente)),
)
def test_generic_authentik_groups_map_to_least_privilege(group, expected):
    assert map_authentik_role({"groups": [group]}) == expected


@pytest.mark.parametrize("groups", (None, 7, {"unexpected": "shape"}))
def test_malformed_group_claim_falls_back_to_client(groups):
    assert map_authentik_role({"groups": groups, "role": "platform_admin"}) == UserRole.cliente


def test_normalize_authentik_identity_trims_tenant_and_maps_operator():
    role, tenant_id = normalize_authentik_identity(
        {"groups": ["operator"], "tenant_id": "  ACME  "}
    )
    assert role == UserRole.helpdesk
    assert tenant_id == "acme"


@pytest.mark.parametrize(
    "claims",
    (
        {"groups": ["viewer"]},
        {"groups": ["operator"], "tenant_id": 123},
        {"groups": ["operator"], "tenant_id": "x" * 129},
    ),
)
def test_normalize_authentik_identity_rejects_missing_or_invalid_tenant(claims):
    with pytest.raises(HTTPException) as error:
        normalize_authentik_identity(claims)
    assert error.value.status_code == 403


def _dependency_calls(dependant):
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from _dependency_calls(dependency)


def test_mounted_api_routes_are_authenticated_and_documented():
    from fastapi.routing import APIRoute

    from app.main import app

    public = {
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/logout"),
        ("POST", "/api/auth/seed"),
        ("POST", "/api/auth/oidc/callback"),
        ("GET", "/api/v1/push/config"),
    }
    matrix = Path(__file__).resolve().parents[3] / "docs/security/access-control-matrix.md"
    content = matrix.read_text(encoding="utf-8")
    documented = set()
    for line in content.splitlines():
        if line.startswith("| ") and " /api/" in line:
            columns = [column.strip() for column in line.strip("| ").split("|")]
            if len(columns) >= 2:
                documented.add((columns[0], columns[1]))

    missing_auth = []
    missing_matrix = []
    for route in app.routes:
        if (
            not isinstance(route, APIRoute)
            or not route.path.startswith("/api/")
            or not route.endpoint.__module__.startswith("app.api.routers.")
        ):
            continue
        for method in route.methods or ():
            key = (method, route.path)
            if key not in public and get_current_user not in set(_dependency_calls(route.dependant)):
                missing_auth.append(f"{method} {route.path}")
            if key not in documented:
                missing_matrix.append(f"{method} {route.path}")

    assert not missing_auth, f"API routes without recognized auth dependency: {missing_auth}"
    assert not missing_matrix, f"API routes missing from access matrix: {missing_matrix}"
