import asyncio

from app.api.routers import core


async def _infra_summary():
    return {
        "hosts_active": 10,
        "agents_rmm": 7,
        "alerts_critical": 2,
        "alerts_total": 5,
        "status": "ok",
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
