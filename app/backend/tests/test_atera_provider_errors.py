from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routers import atera
from app.integrations.atera import AteraClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    (
        lambda: atera.list_customers(),
        lambda: atera.list_agents(),
        lambda: atera.list_alerts(),
        lambda: atera.atera_summary(),
    ),
)
async def test_atera_routes_hide_provider_errors(monkeypatch, operation):
    client = SimpleNamespace(
        list_customers=_raise_provider_error,
        list_agents=_raise_provider_error,
        list_alerts=_raise_provider_error,
        get_dashboard_summary=_raise_provider_error,
    )
    monkeypatch.setattr(atera, "_client", lambda: client)

    with pytest.raises(HTTPException) as error:
        await operation()

    assert error.value.status_code == 502
    assert error.value.detail == "Atera indisponível."
    assert "provider-secret" not in str(error.value.detail)


async def _raise_provider_error(*_args, **_kwargs):
    raise RuntimeError("Bearer provider-secret")


@pytest.mark.asyncio
async def test_atera_dashboard_summary_hides_provider_exception(monkeypatch):
    client = AteraClient(api_key="private-api-key")
    monkeypatch.setattr(client, "_get_page_one", _raise_provider_error)

    result = await client.get_dashboard_summary()

    assert result == {
        "source": "atera",
        "error": "source_unavailable",
        "degraded": True,
    }
