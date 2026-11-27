"""Testes do módulo cf_access — validação de JWT do Cloudflare Access."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.cf_access import validate_cf_access_token


def _fake_jwks_response():
    return {
        "keys": [
            {
                "kid": "test-key-1",
                "kty": "RSA",
                "alg": "RS256",
                "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfA"
                "tVT86zwu1RK7aPECxKEDoEKkf6UqSk1JhFMnBhbW1sdLQBdkCnLQFQjY"
                "m3aBxLJFqQFatg0QmDkHUzJFxyJyGIzRFTGJJRWBmTHGIzF0GJyyGIzNG"
                "GJF0GIyFJTGIzJGGJFQGIzFGJyyGIzNGJFQGIyFGJyyGIzNGJFQGIyFGJ"
                "yyGIzNGJFQGIyFGJyyGIzNGJFQGIyFGJyyGIzNGJFQGIyFGJyyGIzNGJF"
                "QGIyFGJyyGIzDJTGIzHGJF0GIyFJTGIzJGGJFQGIzFGJyyGIzNGJFQGI"
                "yFGJyyGIzNGJFQGIyFGJyyGIzNGJFQGIyFGJyyGIzNGJFQGIyFGJyyGI"
                "zNGJFQGIyFGJyyGIzNGJFQGIyFGJyyGIzNGJFQGIyFGJyyGIzNGJFQGI"
                "yFGJyyGIzNGw",
                "e": "AQAB",
            }
        ]
    }


class FakeJoseJwt:
    """Finge que valida um token qualquer e retorna claims fixas."""

    @staticmethod
    def decode(token, key, algorithms, audience, issuer, options):
        return {
            "email": "ops@ness.com.br",
            "iss": issuer,
            "aud": audience,
            "exp": 9999999999,
        }

    @staticmethod
    def get_unverified_header(token):
        return {"kid": "test-key-1"}


async def test_validate_cf_access_token_success(monkeypatch):
    monkeypatch.setattr(
        "app.core.cf_access.get_settings",
        lambda: type(
            "S",
            (),
            {
                "cf_access_aud": "test-aud",
                "cf_access_team_domain": "test.cloudflareaccess.com",
            },
        )(),
    )

    mock_client = AsyncMock()
    mock_client.get.return_value.json.return_value = _fake_jwks_response()
    mock_client.get.return_value.raise_for_status = lambda: None

    with (
        patch("app.core.cf_access.httpx.AsyncClient", return_value=mock_client),
        patch("app.core.cf_access.jwt", FakeJoseJwt),
    ):
        claims = await validate_cf_access_token("fake-token")

    assert claims["email"] == "ops@ness.com.br"


async def test_validate_cf_access_token_no_aud(monkeypatch):
    monkeypatch.setattr(
        "app.core.cf_access.get_settings",
        lambda: type(
            "S",
            (),
            {"cf_access_aud": "", "cf_access_team_domain": "test.cloudflareaccess.com"},
        )(),
    )

    with pytest.raises(ValueError, match="NINF_CF_ACCESS_AUD"):
        await validate_cf_access_token("fake-token")


async def test_validate_cf_access_token_bad_jwt(monkeypatch):
    monkeypatch.setattr(
        "app.core.cf_access.get_settings",
        lambda: type(
            "S",
            (),
            {
                "cf_access_aud": "test-aud",
                "cf_access_team_domain": "test.cloudflareaccess.com",
            },
        )(),
    )
    monkeypatch.setattr(
        "app.core.cf_access.jwt.get_unverified_header",
        lambda t: (_ for _ in ()).throw(Exception("bad")),
    )

    with pytest.raises(ValueError, match="malformado"):
        await validate_cf_access_token("bad-token")


async def test_middleware_skips_when_disabled():
    from app.core.cf_access_middleware import CloudflareAccessMiddleware
    from starlette.testclient import TestClient
    from fastapi import FastAPI

    app = FastAPI()
    app.add_middleware(CloudflareAccessMiddleware)

    @app.get("/test")
    async def test_route():
        return {"ok": True}

    # CF Access disabled by default (NINF_CF_ACCESS_ENABLED não setada)
    client = TestClient(app)
    r = client.get("/test")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
