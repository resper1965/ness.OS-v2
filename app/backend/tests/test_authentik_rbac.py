from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.dependencies import require_admin, require_noc, require_platform_admin
from app.api.routers.auth import map_authentik_role
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
