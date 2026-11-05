from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.auth import router
from app.core.session import SESSION_COOKIE_NAME
from app.database import get_db


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


def test_oidc_exchange_failure_hides_provider_details(caplog):
    app = FastAPI()
    app.include_router(router)

    with (
        patch(
            "app.api.routers.auth.get_settings",
            return_value=SimpleNamespace(oidc_enabled=True),
        ),
        patch(
            "app.api.routers.auth.exchange_oidc_code",
            new=AsyncMock(side_effect=RuntimeError("code=private")),
        ),
    ):
        response = TestClient(app, base_url="https://hub.ness.com.br").post(
            "/api/auth/oidc/callback",
            headers={"Origin": "https://hub.ness.com.br"},
            json={"code": "test", "redirect_uri": "https://hub.ness.com.br/callback"},
        )

    assert response.status_code == 400
    assert "private" not in response.text
    assert "private" not in caplog.text
