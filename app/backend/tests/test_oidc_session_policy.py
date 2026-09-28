from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.auth import router
from app.core.session import SESSION_COOKIE_NAME
from app.database import get_db
from app.models.users import UserRole


@pytest.mark.parametrize(
    "active,groups,tenant,status",
    [
        (False, ["noc"], "ness", 403),
        (True, ["usuarios"], None, 403),
        (True, ["usuarios"], ["alupar"], 403),
        (True, ["usuarios"], " ALUPAR ", 200),
        (True, ["noc"], None, 200),
        (True, ["operator"], None, 403),
        (True, ["operator"], "tenant-a", 200),
        (True, ["viewer"], None, 403),
        (True, ["viewer"], "tenant-a", 200),
    ],
)
def test_oidc_session_policy(active, groups, tenant, status):
    user = SimpleNamespace(
        id=42,
        email="user@example.invalid",
        full_name="Test",
        role=UserRole.cliente,
        tenant_id="original",
        is_active=active,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: user)
        ),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    app = FastAPI()
    app.include_router(router)

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, base_url="https://hub.ness.com.br")
    claims = {"email": user.email, "groups": groups, "tenant_id": tenant}
    with (
        patch(
            "app.api.routers.auth.get_settings",
            return_value=SimpleNamespace(oidc_enabled=True),
        ),
        patch(
            "app.api.routers.auth.exchange_oidc_code",
            new=AsyncMock(return_value={"id_token": "identity"}),
        ),
        patch(
            "app.api.routers.auth.verify_oidc_token", new=AsyncMock(return_value=claims)
        ),
    ):
        response = client.post(
            "/api/auth/oidc/callback",
            headers={"Origin": "https://hub.ness.com.br"},
            json={"code": "test", "redirect_uri": "https://hub.ness.com.br/callback"},
        )
    assert response.status_code == status
    if status == 200:
        db.commit.assert_awaited_once()
        assert SESSION_COOKIE_NAME in response.cookies
        assert user.tenant_id == (tenant or "").strip().lower()
        if groups[0] in {"operator", "viewer"}:
            assert user.role == UserRole(groups[0])
    else:
        db.commit.assert_not_awaited()
        assert SESSION_COOKIE_NAME not in response.cookies
        assert user.tenant_id == "original"


def test_access_token_cannot_replace_missing_identity_token():
    app = FastAPI()
    app.include_router(router)

    async def override_db():
        yield None

    app.dependency_overrides[get_db] = override_db
    with (
        patch(
            "app.api.routers.auth.get_settings",
            return_value=SimpleNamespace(oidc_enabled=True),
        ),
        patch(
            "app.api.routers.auth.exchange_oidc_code",
            new=AsyncMock(return_value={"access_token": "access"}),
        ),
        patch("app.api.routers.auth.verify_oidc_token", new=AsyncMock()) as verify,
    ):
        response = TestClient(app, base_url="https://hub.ness.com.br").post(
            "/api/auth/oidc/callback",
            headers={"Origin": "https://hub.ness.com.br"},
            json={"code": "test", "redirect_uri": "https://hub.ness.com.br/callback"},
        )
    assert response.status_code == 400
    verify.assert_not_awaited()
    assert SESSION_COOKIE_NAME not in response.cookies
