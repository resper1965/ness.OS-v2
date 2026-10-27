import json

import httpx
import pytest
from pydantic import ValidationError

from app.core import ai_context
from app.integrations import gemini, soc_agent
from app.ml import analyzer

# Synthetic AWS key built at runtime so secret scanners do not flag the fixture.
FAKE_AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
_REAL = {"AsyncClient": httpx.AsyncClient, "Client": httpx.Client}
SECRETS = (
    "S3cr3tPw",
    "dXNlcjpwYXNzd29yZA==",
    "hunter2",
    "tok-123456",
    FAKE_AWS_KEY,
    "sk-live-abc",
    "10.9.8.7",
)
OTHER_TENANT = "ALUPAR-PRIVATE-MARKER"
PLANTED = (
    "login failed password=S3cr3tPw Authorization: Basic dXNlcjpwYXNzd29yZA== "
    "see https://admin:hunter2@vault.internal/x token=tok-123456 "
    '{"api_key":"sk-live-abc"} ' + FAKE_AWS_KEY + " from 10.9.8.7"
)
OK_RESPONSE = {
    "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
    "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3},
}


def _capture(monkeypatch, client_name):
    bodies = []

    def handler(request):
        bodies.append(request.content.decode() + "\n" + str(request.url))
        return httpx.Response(200, json=OK_RESPONSE)

    original = _REAL[client_name]
    monkeypatch.setattr(
        httpx,
        client_name,
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    return bodies


def _assert_clean(bodies):
    assert bodies
    sent = "\n".join(bodies)
    for leaked in (*SECRETS, OTHER_TENANT):
        assert leaked not in sent


@pytest.mark.asyncio
async def test_gemini_payload_has_no_secrets_or_other_tenant(monkeypatch):
    for module in (analyzer.settings, soc_agent.settings, gemini.settings):
        monkeypatch.setattr(module, "gemini_api_key", "synthetic-key")

    # Incident analysis (alert worker)
    bodies = _capture(monkeypatch, "AsyncClient")
    await analyzer.analyze_incident(
        {
            "event_id": "77",
            "host_name": "srv-01",
            "trigger_name": PLANTED,
            "trigger_description": PLANTED,
            "severity": 4,
            "tags": {"ninf_customer_name": OTHER_TENANT},
            "items": [{"value": OTHER_TENANT}],
        },
        {"customer_name": "Cavan", "other": OTHER_TENANT},
    )
    _assert_clean(bodies)

    # SOC triage (Wazuh)
    bodies = _capture(monkeypatch, "Client")
    soc_agent.triage_wazuh_alert(
        {
            "id": "1700.1",
            "timestamp": "2026-10-26T10:00:00.000+0000",
            "rule": {"id": "100201", "level": 12, "description": PLANTED},
            "agent": {
                "id": "002",
                "name": "dc-01",
                "ip": "10.9.8.7",
                "group": ["cavan"],
            },
            "full_log": PLANTED,
            "data": {"password": "S3cr3tPw", "note": PLANTED},
            "manager": {"name": OTHER_TENANT},
            "cluster": {"node": OTHER_TENANT},
        }
    )
    _assert_clean(bodies)

    # Post-mortem (similar incidents from another tenant are available)
    bodies = _capture(monkeypatch, "Client")
    gemini.generate_postmortem(
        {
            "fingerprint": "fp",
            "customer_name": "Cavan",
            "title": "CPU",
            "trigger_description": PLANTED,
            "tags": {"x": OTHER_TENANT},
        },
        [{"value": 1, "token": "tok-123456"}],
        [PLANTED],
        [{"customer_name": "Alupar", "root_cause": OTHER_TENANT}],
    )
    _assert_clean(bodies)


@pytest.mark.asyncio
async def test_analyzer_payload_validates_against_schema(monkeypatch):
    monkeypatch.setattr(analyzer.settings, "gemini_api_key", "synthetic-key")
    bodies = _capture(monkeypatch, "AsyncClient")
    await analyzer.analyze_incident(
        {"event_id": "77", "timestamp": "2026-10-26T10:00:00Z", "severity": 5},
        {"customer_name": "Cavan"},
    )
    text = json.loads(bodies[0].split("\nhttps://")[0])["contents"][0]["parts"][0][
        "text"
    ]
    raw = text.split("# Dados do Incidente:\n")[1].split("\n\n# Escopo")[0]
    request = ai_context.AIRequestV1.model_validate_json(raw)
    assert (request.tenant, request.source_event_id) == ("Cavan", "77")
    assert request.observed_at.year == 2026


def test_ai_request_schema_is_strict():
    base = {
        "tenant": "Cavan",
        "source_event_id": "1",
        "severity": "4",
        "observed_at": "2026-10-26T10:00:00Z",
        "evidence": {"password": "x", "note": "token=abc"},
    }
    clean = ai_context.AIRequestV1(**base)
    assert "abc" not in json.dumps(clean.evidence) and clean.evidence["password"] != "x"
    with pytest.raises(ValidationError):
        ai_context.AIRequestV1(**base, extra_field=1)
    with pytest.raises(ValidationError):
        ai_context.AIRequestV1(**{**base, "tenant": ""})


@pytest.mark.asyncio
async def test_ai_call_metrics_logged(monkeypatch, caplog):
    monkeypatch.setattr(analyzer.settings, "gemini_api_key", "synthetic-key")
    _capture(monkeypatch, "AsyncClient")
    caplog.set_level("INFO")
    await analyzer.analyze_incident({"severity": 4})  # "{}" -> invalid analysis
    line = next(r.message for r in caplog.records if "ai_call" in r.message)
    data = json.loads(line.split("ai_call ", 1)[1])
    assert data["kind"] == "incident_analysis" and data["outcome"] == "error"
    assert data["latency_ms"] >= 0 and data["prompt_tokens"] == 7


def test_invalid_wazuh_timestamp_falls_back_without_exception(monkeypatch, caplog):
    monkeypatch.setattr(soc_agent.settings, "gemini_api_key", "synthetic-key")
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(503)

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: _REAL["Client"](transport=httpx.MockTransport(handler), **kw),
    )
    result = soc_agent.triage_wazuh_alert(
        {"rule": {"id": "1", "level": 12}, "timestamp": "not-a-date"}
    )
    assert sent  # request was built from the invalid timestamp and sent
    assert result["classification"] == "HIGH"  # provider failure -> fallback
    assert "observed_at unparseable" in caplog.text


def test_google_key_and_jwt_are_redacted_but_bypass_secretary_are_not():
    from app.core.sanitizer import sanitize

    google = "AIza" + "A" * 35
    jwt = "eyJhbGciOiJI.eyJzdWIiOiIx.c2lnbmF0dXJl"
    clean = sanitize(f"k {google} j {jwt}")
    assert google not in clean and jwt not in clean
    text = "bypass: enabled secretary=ana mypass=ok"
    assert sanitize(text) == text
