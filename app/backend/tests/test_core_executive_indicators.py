import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.api.routers import core


async def _infra_summary():
    return {
        "hosts_active": 10,
        "agents_rmm": 7,
        "alerts_critical": 2,
        "alerts_total": 5,
        "status": "ok",
        "sources": {"zabbix": {"status": "ok"}, "atera": {"status": "ok"}},
    }


async def _secops_summary():
    return {
        "incidents_open": 3,
        "incidents_critical": 1,
        "agents_online": 4,
        "status": "ok",
    }


def test_overview_does_not_publish_unapproved_health_score(monkeypatch):
    monkeypatch.setattr(core, "_infra_summary", _infra_summary)
    monkeypatch.setattr(core, "_secops_summary", _secops_summary)

    result = asyncio.run(core.get_overview())

    assert result["health_score"] is None
    assert result["health_score_status"] == "provisional"
    assert result["health_score_reason"]


def test_kpis_keep_sources_separate_instead_of_double_counting(monkeypatch):
    monkeypatch.setattr(core, "_infra_summary", _infra_summary)
    monkeypatch.setattr(core, "_secops_summary", _secops_summary)

    result = asyncio.run(core.get_kpis())
    kpis = {item["id"]: item for item in result["kpis"]}

    assert "total_assets" not in kpis
    assert "total_open_issues" not in kpis
    assert kpis["zabbix_hosts_active"]["value"] == 10
    assert kpis["zabbix_hosts_active"]["source"] == "zabbix"
    assert kpis["rmm_agents_reported"]["value"] == 7
    assert kpis["rmm_agents_reported"]["source"] == "atera"
    assert kpis["secops_incidents_open"]["value"] == 3


def test_kpis_do_not_report_provider_failure_as_zero(monkeypatch):
    async def failed_call(*_args, **_kwargs):
        raise RuntimeError("provider secret")

    monkeypatch.setattr(
        core, "ZabbixClient", lambda: SimpleNamespace(_call=failed_call)
    )
    monkeypatch.setattr(core, "get_settings", lambda: SimpleNamespace(atera_api_key=""))

    infra = asyncio.run(core._infra_summary())

    assert infra["hosts_active"] is None
    assert infra["alerts_total"] is None
    assert infra["sources"]["zabbix"]["status"] == "unavailable"
    assert infra["sources"]["atera"] == {
        "status": "unavailable",
        "error_code": "not_configured",
    }

    async def unavailable_infra_summary():
        return infra

    monkeypatch.setattr(core, "_infra_summary", unavailable_infra_summary)
    kpis = {item["id"]: item for item in asyncio.run(core.get_kpis())["kpis"]}

    assert kpis["zabbix_hosts_active"]["value"] is None
    assert kpis["zabbix_hosts_active"]["status"] == "unavailable"
    assert kpis["zabbix_alerts_critical"]["alert"] is None


def test_infra_summary_uses_atera_dashboard_contract(monkeypatch):
    async def zabbix_call(method, _params):
        return [] if method == "host.get" else []

    atera_client = SimpleNamespace(
        get_dashboard_summary=AsyncMock(
            return_value={"agents_total": 7, "alerts_total": 2}
        )
    )
    monkeypatch.setattr(
        core, "ZabbixClient", lambda: SimpleNamespace(_call=zabbix_call)
    )
    monkeypatch.setattr(core, "AteraClient", lambda **_kwargs: atera_client)
    monkeypatch.setattr(
        core, "get_settings", lambda: SimpleNamespace(atera_api_key="key")
    )

    result = asyncio.run(core._infra_summary())

    assert result["agents_rmm"] == 7
    assert result["rmm_alerts"] == 2
    assert result["sources"]["atera"]["status"] == "ok"
    atera_client.get_dashboard_summary.assert_awaited_once()
