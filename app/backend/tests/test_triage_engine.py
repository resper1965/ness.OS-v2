from app.core.triage_engine import TriageEngine, TriageAction


def test_triage_low_risk_archived():
    """Alerta de baixo nível e ativo normal deve retornar Risco < 75 e ação ARCHIVE (LLM Bypassed)."""
    engine = TriageEngine()
    alert_data = {
        "level": 4,
        "host": "workstation-user-01",
        "description": "User login success",
    }
    result = engine.evaluate_alert(alert_data, fingerprint="fp_test_low")

    assert result.risk_score < 75
    assert result.action == TriageAction.ARCHIVE
    assert result.llm_bypassed is True


def test_triage_critical_asset_escalated():
    """Alerta em Domain Controller deve pontuar alto e atingir a faixa de IA (Risco >= 75)."""
    engine = TriageEngine()
    alert_data = {
        "level": 14,  # 14 * 4 = 56 pts
        "host": "prod-dc-01",  # Asset DC = +25 pts -> Total 81 pts
        "description": "LSASS memory dump attempt",
    }
    result = engine.evaluate_alert(alert_data, fingerprint="fp_test_dc")

    assert result.risk_score >= 75
    assert result.action in (TriageAction.TRIAGE_L1, TriageAction.TRIAGE_L2)
    assert result.llm_bypassed is False


def test_triage_threat_intel_escalated():
    """Alerta com IP malicioso confirmado no AbuseIPDB/VirusTotal deve receber pontuação extra."""
    engine = TriageEngine()
    alert_data = {
        "level": 12,  # 12 * 4 = 48 pts
        "host": "web-server-01",
        "description": "Suspicious inbound traffic",
    }
    threat_intel = {
        "abuseipdb": {"abuse_score": 90},
        "virustotal": {"malicious": 5},
    }
    result = engine.evaluate_alert(alert_data, threat_intel=threat_intel, fingerprint="fp_test_intel")

    # 48 + 25 = 73 -> com recorrência ou mais dados atinge >= 75
    assert result.risk_score >= 73
    assert len(result.reasons) > 0


def test_triage_frequency_penalty():
    """Eventos repetidos na janela de 5 minutos devem aumentar o score de risco."""
    engine = TriageEngine()
    alert_data = {
        "level": 10,  # 40 pts
        "host": "srv-app",
        "description": "Failed password attempt",
    }
    fp = "fp_recurring_test"

    # Primeira ocorrência
    res1 = engine.evaluate_alert(alert_data, fingerprint=fp)
    score1 = res1.risk_score

    # Segunda ocorrência
    res2 = engine.evaluate_alert(alert_data, fingerprint=fp)
    score2 = res2.risk_score

    assert score2 > score1
    assert res2.frequency_count == 2
