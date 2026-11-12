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


def _callback_with_claims(claims):
    app = FastAPI()
    app.include_router(router)

    class _Db:
        async def execute(self, *_):
            return SimpleNamespace(scalar_one_or_none=lambda: None)

    async def override_db():
        yield _Db()

    app.dependency_overrides[get_db] = override_db
    with (
        patch(
            "app.api.routers.auth.get_settings",
            return_value=SimpleNamespace(oidc_enabled=True),
        ),
        patch(
            "app.api.routers.auth.exchange_oidc_code",
            new=AsyncMock(return_value={"id_token": "id"}),
        ),
        patch(
            "app.api.routers.auth.verify_oidc_token",
            new=AsyncMock(return_value=claims),
        ),
    ):
        return TestClient(app, base_url="https://hub.ness.com.br").post(
            "/api/auth/oidc/callback",
            headers={"Origin": "https://hub.ness.com.br"},
            json={"code": "test", "redirect_uri": "https://hub.ness.com.br/callback"},
        )


ENTRA_ISS = (
    "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0"
)


def test_entra_token_without_oid_is_rejected():
    response = _callback_with_claims({"iss": ENTRA_ISS, "sub": "per-app-sub"})
    assert response.status_code == 401
    assert SESSION_COOKIE_NAME not in response.cookies


def test_entra_token_uses_oid_and_unlinked_gets_403(caplog):
    response = _callback_with_claims(
        {"iss": ENTRA_ISS, "sub": "per-app-sub", "oid": "object-id"}
    )
    assert response.status_code == 403
    assert "object-id" in caplog.text
