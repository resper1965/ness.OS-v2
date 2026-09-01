from unittest.mock import AsyncMock, patch

import pytest

from app.core.oidc import exchange_oidc_code


class _Response:
    is_success = True

    def json(self):
        return {"id_token": "test-token"}


@pytest.mark.asyncio
async def test_exchange_oidc_code_forwards_pkce_verifier():
    client = AsyncMock()
    client.post.return_value = _Response()
    client.__aenter__.return_value = client

    with patch("app.core.oidc.httpx.AsyncClient", return_value=client):
        await exchange_oidc_code("code", "https://hub/callback", "verifier")

    payload = client.post.await_args.kwargs["data"]
    assert payload["code_verifier"] == "verifier"


@pytest.mark.asyncio
async def test_exchange_oidc_code_preserves_legacy_transition_without_pkce():
    client = AsyncMock()
    client.post.return_value = _Response()
    client.__aenter__.return_value = client

    with patch("app.core.oidc.httpx.AsyncClient", return_value=client):
        await exchange_oidc_code("code", "https://hub/callback")

    payload = client.post.await_args.kwargs["data"]
    assert "code_verifier" not in payload
