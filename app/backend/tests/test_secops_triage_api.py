from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.routers import secops as _secops
from app.core.dependencies import get_current_user
from app.database import get_db
from app.main import app
from app.models.users import UserRole

client = TestClient(app)
_real_resolve_tenant = _secops._resolve_tenant  # autouse fixture stubs the module attr


class _Actions:
    def __init__(self, values: list[str]):
        self.values = values

    def all(self) -> list[str]:
        return self.values


class _StatsResult:
    def __init__(self, values: list[str]):
        self.values = values

    def scalars(self) -> _Actions:
        return _Actions(self.values)


@pytest.fixture(autouse=True)
def authenticated_soc():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=7,
        role=UserRole.soc,
        tenant_id=None,
    )
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def persisted_triage_stats_database():
    session = AsyncMock()
    session.execute.return_value = _StatsResult(
        ["ARCHIVE_NO_LLM", "Review required", "ARCHIVE_NO_LLM"]
    )

    async def database():
        yield session

    app.dependency_overrides[get_db] = database
    yield session
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def mapped_tenant(monkeypatch):
    """Vínculo administrativo resolvido; os testes de pendência sobrescrevem."""
    from app.api.routers import secops

    async def resolved(db, payload):
        return "cavan"

    monkeypatch.setattr(secops, "_resolve_tenant", resolved)


@pytest.fixture
def decision_database():
    session = AsyncMock()
    session.add = MagicMock(side_effect=lambda decision: setattr(decision, "id", 19))

    async def database():
        yield session

    app.dependency_overrides[get_db] = database
    yield session
    app.dependency_overrides.pop(get_db, None)


def test_triage_stats_endpoint(persisted_triage_stats_database):
    """Estatísticas sobrevivem ao processo porque são derivadas das decisões salvas."""
    response = client.get("/api/secops/triage-stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_processed" in data
    assert "llm_bypassed_count" in data
    assert "bypassed_percentage" in data
    assert data["total_processed"] == 3
    assert data["llm_bypassed_count"] == 2
    assert data["llm_called_count"] == 1
    assert data["bypassed_percentage"] == 66.67
    assert data["target_meta_percentage"] == 95.0
    persisted_triage_stats_database.execute.assert_awaited_once()


def test_triage_stats_without_decisions_are_unavailable(
    persisted_triage_stats_database,
):
    persisted_triage_stats_database.execute.return_value = _StatsResult([])

    response = client.get("/api/secops/triage-stats")

    assert response.status_code == 200
    assert response.json()["total_processed"] == 0
    assert response.json()["bypassed_percentage"] is None
    assert response.json()["status"] == "unavailable"


def test_triage_alert_low_risk_bypasses_llm(decision_database):
    """Alerta com Wazuh level 3 e host comum deve ter o LLM Bypassed pelo Triage Worker (Camada 4)."""
    payload = {
        "rule": {"id": "100200", "level": 3},
        "agent": {"id": "001", "name": "workstation-10", "group": ["default"]},
        "description": "User login succeeded",
    }

    response = client.post("/api/secops/triage", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["action_taken"] == "ARCHIVE_NO_LLM"
    assert data["classification"] == "LOW_PRIORITY"
    assert data["llm_bypassed"] is True
    assert data["risk_score"] < 75
    assert data["decision_id"] == 19
    assert data["dispatch_status"] == "not_requested"
    decision_database.commit.assert_awaited_once()


def test_triage_alert_uses_nested_wazuh_fields_and_enrichment(
    decision_database, monkeypatch
):
    from app.api.routers import secops

    async def malicious_ip(_ip: str):
        return {
            "ip": "203.0.113.10",
            "abuseipdb": {"abuse_score": 90},
            "virustotal": {"malicious": 4},
            "misp": {"found": True, "match_count": 1},
        }

    monkeypatch.setattr(
        secops, "_extract_ips_and_hashes", lambda payload: (["203.0.113.10"], [])
    )
    monkeypatch.setattr("app.integrations.threat_intel.enrich_ip", malicious_ip)

    async def fake_triage(payload, tenant):
        assert tenant == "cavan"
        return {
            "classification": "MALICIOUS",
            "confidence": 0.9,
            "summary": "Malicious IOC",
            "action_taken": "Escalated",
        }

    monkeypatch.setattr("app.integrations.soc_agent.triage_wazuh_alert", fake_triage)

    response = client.post(
        "/api/secops/triage",
        json={
            "rule": {"id": "100201", "level": 15},
            "agent": {"id": "002", "name": "prod-dc-01", "group": ["cavan"]},
        },
    )

    assert response.status_code == 200
    assert response.json()["risk_score"] == 100
    assert response.json()["llm_bypassed"] is False


def _spy_triage(monkeypatch):
    calls = []

    async def fake(payload, tenant):
        calls.append(tenant)
        return {
            "classification": "LOW",
            "confidence": 0.9,
            "summary": "s",
            "action_taken": "a",
        }

    monkeypatch.setattr("app.integrations.soc_agent.triage_wazuh_alert", fake)
    monkeypatch.setattr(
        "app.integrations.n8n.notify_soc_triage_decision",
        lambda p: calls.append(("n8n", p["customer_id"])) or {"status": "sent"},
    )
    return calls


@pytest.mark.parametrize("level,attended", [(3, False), (11, False), (12, True)])
def test_attendance_floor_is_independent_of_score_and_model(
    decision_database, monkeypatch, level, attended
):
    calls = _spy_triage(monkeypatch)
    payload = {
        "rule": {"id": "1", "level": level},
        "agent": {"id": "1", "name": "workstation-10", "group": ["g"]},
    }
    data = client.post("/api/secops/triage", json=payload).json()
    assert data["attendance_required"] is attended
    assert (("n8n", "cavan") in calls) is attended


def test_attended_alert_is_dispatched_even_if_model_fails(
    decision_database, monkeypatch
):
    from app.integrations import soc_agent

    monkeypatch.setattr(soc_agent.settings, "llm_api_key", "")
    sent = []
    monkeypatch.setattr(
        "app.integrations.n8n.notify_soc_triage_decision",
        lambda p: sent.append(p) or {"status": "sent"},
    )
    payload = {
        "rule": {"id": "1", "level": 15},
        "agent": {"id": "1", "name": "workstation-10", "group": ["g"]},
    }
    data = client.post("/api/secops/triage", json=payload).json()
    assert data["classification"] == "HIGH" and data["dispatch_status"] == "sent"
    assert sent and sent[0]["customer_id"] == "cavan"


def test_unmapped_tenant_is_pending_without_enrichment_or_llm(
    decision_database, monkeypatch
):
    from app.api.routers import secops

    async def unresolved(db, payload):
        return None

    async def forbidden(*a, **k):
        raise AssertionError("no external call without a tenant")

    calls = _spy_triage(monkeypatch)
    monkeypatch.setattr(secops, "_resolve_tenant", unresolved)
    monkeypatch.setattr(
        secops, "_extract_ips_and_hashes", lambda p: (["203.0.113.10"], ["a" * 64])
    )
    monkeypatch.setattr("app.integrations.threat_intel.enrich_ip", forbidden)
    monkeypatch.setattr("app.integrations.threat_intel.enrich_hash", forbidden)
    payload = {
        "rule": {"id": "1", "level": 3},
        "agent": {"id": "1", "name": "x", "group": ["default"]},
    }
    data = client.post("/api/secops/triage", json=payload).json()
    assert data["action_taken"] == "PENDING_TENANT_REVIEW"
    assert data["classification"] == "PENDING_REVIEW"
    assert data["attendance_required"] is True
    assert [c for c in calls if c != ("n8n", None)] == []  # no LLM, no tenant
    decision = decision_database.add.call_args.args[0]
    assert decision.customer_id is None


class _Rows:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return self.values


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent,rows,expected",
    [
        ({"group": ["cavan"]}, ["c1"], "c1"),
        ({"group": ["a", "b"]}, ["c1", "c2"], None),  # ambiguous
        ({"group": ["x"]}, [], None),  # unmapped
        ({"group": []}, ["c1"], None),  # no group: no lookup
        ({}, ["c1"], None),
        ({"group": [None, 3]}, ["c1"], None),
    ],
)
async def test_resolve_tenant(agent, rows, expected):
    db = AsyncMock()
    db.execute.return_value = _Rows(rows)
    assert await _real_resolve_tenant(db, {"agent": agent}) == expected
