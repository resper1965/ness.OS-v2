import pytest
from fastapi import HTTPException

from app.api.routers import assets


class FailingAtera:
    async def get_dashboard_summary(self):
        raise RuntimeError("Bearer provider-secret")


@pytest.mark.asyncio
async def test_assets_summary_does_not_expose_provider_error(monkeypatch):
    monkeypatch.setattr(assets, "_atera", lambda: FailingAtera())

    with pytest.raises(HTTPException) as error:
        await assets.get_assets_summary()

    assert error.value.status_code == 502
    assert error.value.detail == "Atera indisponível."


@pytest.mark.asyncio
async def test_assets_count_returns_safe_degraded_status(monkeypatch):
    monkeypatch.setattr(assets, "_atera", lambda: FailingAtera())

    assert await assets.count_assets() == {
        "atera": 0,
        "datto": 0,
        "total": 0,
        "error": "atera_unavailable",
    }
