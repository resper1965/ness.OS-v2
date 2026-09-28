from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.database import get_db
from app.main import app
from app.models.users import UserRole

client = TestClient(app)


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
    monkeypatch.setattr(
        "app.integrations.soc_agent.triage_wazuh_alert",
        lambda payload: {
            "classification": "MALICIOUS",
            "confidence": 0.9,
            "summary": "Malicious IOC",
            "action_taken": "Escalated",
        },
    )

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
