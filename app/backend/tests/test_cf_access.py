"""Testes do módulo cf_access — validação de JWT do Cloudflare Access."""

import time
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

from app.core import cf_access
from app.core.cf_access import validate_cf_access_token

pytestmark = pytest.mark.asyncio

TEAM = "test.cloudflareaccess.com"
AUD = "test-aud"


def _keypair(kid):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public = jwk.construct(
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode(),
        "RS256",
    ).to_dict()
    return pem, {**public, "kid": kid}


def _token(pem, kid="k1", **overrides):
    claims = {
        "email": "ops@ness.com.br",
        "iss": f"https://{TEAM}",
        "aud": AUD,
        "exp": int(time.time()) + 300,
        **overrides,
    }
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


@pytest.fixture
def setup(monkeypatch):
    pem, public = _keypair("k1")
    monkeypatch.setattr(
        cf_access,
        "get_settings",
        lambda: SimpleNamespace(cf_access_aud=AUD, cf_access_team_domain=TEAM),
    )

    async def fake_fetch(client, team_domain):
        return [public]

    monkeypatch.setattr(cf_access, "_fetch_jwks", fake_fetch)
    return pem


async def test_valid_token(setup):
    claims = await validate_cf_access_token(_token(setup))
    assert claims["email"] == "ops@ness.com.br"


async def test_wrong_audience_rejected(setup):
    with pytest.raises(ValueError, match="claims inválidas"):
        await validate_cf_access_token(_token(setup, aud="outra-app"))


async def test_expired_rejected(setup):
    with pytest.raises(ValueError, match="expirado"):
        await validate_cf_access_token(_token(setup, exp=int(time.time()) - 10))


async def test_token_signed_by_other_key_rejected(setup):
    other_pem, _ = _keypair("k1")
    with pytest.raises(ValueError, match="inválido"):
        await validate_cf_access_token(_token(other_pem))


async def test_unknown_kid_rejected(setup):
    with pytest.raises(ValueError, match="não encontrada"):
        await validate_cf_access_token(_token(setup, kid="desconhecido"))


async def test_malformed_token_rejected(setup):
    with pytest.raises(ValueError, match="malformado"):
        await validate_cf_access_token("nao-e-jwt")


async def test_missing_aud_config_rejected(monkeypatch):
    monkeypatch.setattr(
        cf_access,
        "get_settings",
        lambda: SimpleNamespace(cf_access_aud="", cf_access_team_domain=TEAM),
    )
    with pytest.raises(ValueError, match="NINF_CF_ACCESS_AUD"):
        await validate_cf_access_token("x")


def _app():
    from fastapi import FastAPI

    from app.core.cf_access_middleware import CloudflareAccessMiddleware

    app = FastAPI()
    app.add_middleware(CloudflareAccessMiddleware)
    for path in ("/api/x", "/webhook/zabbix", "/v1/alerts", "/api/secops/ingest/wazuh"):
        app.get(path)(lambda: {"ok": True})
    return app


@pytest.mark.parametrize(
    "path,status",
    [
        ("/api/x", 401),
        ("/webhook/zabbix", 200),
        ("/v1/alerts", 200),
        ("/api/secops/ingest/wazuh", 200),
    ],
)
def test_middleware_enabled_exige_jwt_so_em_rota_humana(monkeypatch, path, status):
    from starlette.testclient import TestClient

    monkeypatch.setattr(
        "app.core.cf_access_middleware.get_settings",
        lambda: SimpleNamespace(cf_access_enabled=True),
    )
    assert TestClient(_app()).get(path).status_code == status


def test_middleware_desligado_nao_exige_nada(monkeypatch):
    from starlette.testclient import TestClient

    monkeypatch.setattr(
        "app.core.cf_access_middleware.get_settings",
        lambda: SimpleNamespace(cf_access_enabled=False),
    )
    assert TestClient(_app()).get("/api/x").status_code == 200


async def test_access_login_cria_sessao_com_papel_do_banco(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from app.api.routers import auth
    from app.models.users import UserRole

    user = SimpleNamespace(
        id=7,
        email="Ops@ness.com.br",
        full_name="Ops",
        is_active=True,
        role=UserRole.cliente,
        tenant_id="t1",
        session_epoch=0,
        last_login=None,
    )
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none = lambda: user
    monkeypatch.setattr(auth, "require_trusted_origin", lambda r: None)
    monkeypatch.setattr(
        auth, "get_settings", lambda: SimpleNamespace(cf_access_enabled=True)
    )
    monkeypatch.setattr(
        auth,
        "validate_cf_access_token",
        AsyncMock(return_value={"email": "ops@ness.com.br"}),
    )
    monkeypatch.setattr(auth, "create_access_token", lambda **k: "tok")
    monkeypatch.setattr(auth, "set_session_cookie", MagicMock())
    req = SimpleNamespace(headers={"Cf-Access-Jwt-Assertion": "jwt"})
    out = await auth.access_login(req, MagicMock(), db)
    assert out.role == "cliente" and out.email == "Ops@ness.com.br"


async def test_access_login_usuario_desconhecido_403(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from fastapi import HTTPException

    from app.api.routers import auth

    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none = lambda: None
    monkeypatch.setattr(auth, "require_trusted_origin", lambda r: None)
    monkeypatch.setattr(
        auth, "get_settings", lambda: SimpleNamespace(cf_access_enabled=True)
    )
    monkeypatch.setattr(
        auth, "validate_cf_access_token", AsyncMock(return_value={"email": "x@y.com"})
    )
    req = SimpleNamespace(headers={"Cf-Access-Jwt-Assertion": "jwt"})
    with pytest.raises(HTTPException) as e:
        await auth.access_login(req, MagicMock(), db)
    assert e.value.status_code == 403
