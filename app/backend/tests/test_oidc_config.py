from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.auth import router


def test_oidc_config_exposes_public_fields_only():
    app = FastAPI()
    app.include_router(router)
    cfg = SimpleNamespace(
        oidc_enabled=True,
        oidc_client_id="cid",
        oidc_client_secret="NAO-VAZAR",
        oidc_authorize_url="https://login.microsoftonline.com/t/oauth2/v2.0/authorize",
        oidc_logout_url="https://login.microsoftonline.com/t/oauth2/v2.0/logout",
        oidc_scope="openid profile email",
    )
    with patch("app.api.routers.auth.get_settings", return_value=cfg):
        r = TestClient(app).get("/api/auth/oidc/config")
    assert r.status_code == 200
    assert r.json()["client_id"] == "cid" and r.json()["enabled"] is True
    assert "NAO-VAZAR" not in r.text
