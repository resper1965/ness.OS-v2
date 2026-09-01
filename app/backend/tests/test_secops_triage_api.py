from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_triage_stats_endpoint():
    """Verifica se o endpoint GET /api/secops/triage-stats retorna estatísticas válidas."""
    response = client.get("/api/secops/triage-stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_processed" in data
    assert "llm_bypassed_count" in data
    assert "bypassed_percentage" in data
    assert data["target_meta_percentage"] == 95.0


def test_triage_alert_low_risk_bypasses_llm():
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
    assert data["llm_bypassed"] is True
    assert data["risk_score"] < 75
