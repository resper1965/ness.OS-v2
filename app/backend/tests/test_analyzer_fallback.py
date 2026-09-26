import httpx
import pytest

from app.ml import analyzer


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["quota", "timeout", "invalid_json"])
@pytest.mark.parametrize(
    "severity,urgency", [(3, "MEDIUM"), (4, "HIGH"), (5, "CRITICAL")]
)
async def test_provider_failure_returns_manual_triage_without_isolation(
    monkeypatch, failure, severity, urgency
):
    monkeypatch.setattr(analyzer.settings, "gemini_api_key", "synthetic-key")

    def handler(request):
        assert request.headers["x-goog-api-key"] == "synthetic-key"
        assert "synthetic-key" not in str(request.url)
        if failure == "timeout":
            raise httpx.ReadTimeout("Synthetic timeout", request=request)
        if failure == "quota":
            return httpx.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}})
        return httpx.Response(200, json={"candidates": []})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    result = await analyzer.analyze_incident(
        {"host_name": "synthetic", "trigger_name": "test", "severity": severity}
    )
    assert "Triagem manual" in result.probable_cause
    assert result.isolation_required is False
    assert "synthetic" in result.executive_action_plan
    assert result.urgency == urgency


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "severity,urgency",
    [
        ("DISASTER", "CRITICAL"),
        ("4", "HIGH"),
        (1, "LOW"),
        (None, "MEDIUM"),
        (0, "MEDIUM"),
    ],
)
async def test_missing_key_preserves_source_priority_without_http(
    monkeypatch, severity, urgency
):
    monkeypatch.setattr(analyzer.settings, "gemini_api_key", "")

    def forbidden(**kwargs):
        raise AssertionError("No provider call without configured credentials")

    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    result = await analyzer.analyze_incident({"severity": severity})
    assert result.urgency == urgency
    assert result.isolation_required is False
    assert "Triagem manual" in result.probable_cause


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ai_urgency,expected,manual",
    [
        ("LOW", "CRITICAL", False),
        ("CRITICAL", "CRITICAL", False),
        ("URGENT", "CRITICAL", True),
    ],
)
async def test_model_cannot_downgrade_critical_event(
    monkeypatch, ai_urgency, expected, manual
):
    import json

    monkeypatch.setattr(analyzer.settings, "gemini_api_key", "synthetic-key")
    payload = {
        "executive_action_plan": "Review impact",
        "technical_action_plan": "Review logs",
        "urgency": ai_urgency,
        "isolation_required": False,
        "probable_cause": "Unconfirmed hypothesis",
        "recommended_playbook": "Default Troubleshooting",
    }
    original = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]
            },
        )
    )
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs)
    )
    result = await analyzer.analyze_incident({"severity": 5})
    assert result.urgency == expected
    assert ("Triagem manual" in result.probable_cause) is manual
