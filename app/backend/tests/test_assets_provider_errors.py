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
        "atera": None,
        "datto": None,
        "total": None,
        "status": "unavailable",
        "error_code": "source_unavailable",
    }


@pytest.mark.asyncio
async def test_assets_do_not_report_zero_when_atera_is_not_configured(monkeypatch):
    monkeypatch.setattr(assets, "_atera", lambda: None)

    assert await assets.get_assets_summary() == {
        "atera": {
            "total": None,
            "customers": None,
            "alerts": None,
            "status": "unavailable",
            "error_code": "not_configured",
        },
        "datto": {"total": None, "status": "planned"},
    }
    assert await assets.count_assets() == {
        "atera": None,
        "datto": None,
        "total": None,
        "status": "unavailable",
        "error_code": "not_configured",
    }


@pytest.mark.asyncio
async def test_assets_list_hides_missing_configuration(monkeypatch):
    monkeypatch.setattr(assets, "_atera", lambda: None)

    with pytest.raises(HTTPException) as error:
        await assets.list_assets()

    assert error.value.status_code == 503
    assert error.value.detail == "Atera indisponível."
