import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core import ai_context
from app.core.sanitizer import sanitize_dict
from app.integrations import gemini, llm
from app.ml import analyzer
from app.workers import postmortem


def test_nested_secrets_and_input_are_preserved_separately():
    source = {
        "items": [
            {
                "password": {"value": "secret-one"},
                "nested": [[{"api-key": "secret-two"}]],
            }
        ],
        "Authorization": ["secret-three"],
    }
    clean = sanitize_dict(source)
    assert "secret-" not in json.dumps(clean)
    assert source["Authorization"] == ["secret-three"]


def test_prompt_drops_metadata_and_other_tenant_reports():
    prompt = gemini.build_postmortem_prompt(
        {
            "title": "CPU pressure",
            "customer_name": "Cavan",
            "credentials": {"password": "s1"},
            "tags": {"other_customer": "private-metadata"},
        },
        [{"value": 99, "nested": [{"token": "s2"}]}],
        ["password=s3"],
        [
            {"customer_name": "Alupar", "root_cause": "other-tenant-private"},
            {"customer_name": "Cavan", "root_cause": "same-tenant-evidence"},
        ],
    )
    for secret in ("s1", "s2", "s3", "private-metadata", "other-tenant-private"):
        assert secret not in prompt
    assert "same-tenant-evidence" in prompt
    assert "CPU pressure" in prompt


@pytest.mark.asyncio
async def test_analyzer_uses_allowlisted_context(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_api_key", "synthetic-key")

    def handler(request):
        content = request.content.decode()
        for secret in ("item-secret", "customer-secret", "tag-secret"):
            assert secret not in content
        assert "CPU pressure" in content
        return httpx.Response(429)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    await analyzer.analyze_incident(
        {
            "trigger_name": "CPU pressure",
            "items": [{"value": "item-secret"}],
            "tags": {"x": "tag-secret"},
        },
        {"password": "customer-secret"},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["missing", "unknown_customer", "different_asset", "wrong_ticket", "valid"]
)
async def test_postmortem_uses_authoritative_identity(monkeypatch, case):
    incident = SimpleNamespace(
        fingerprint="fp",
        tags={"ninf_customer_name": "Cavan"},
        asset=SimpleNamespace(customer_name="Cavan"),
        deskmanager_ticket_id="7",
        host_id="10882",
        host_name="real-host",
        title="real-title",
        trigger_id="9",
        sanitized_description="safe",
        severity=5,
        status="open",
    )
    if case == "unknown_customer":
        incident.tags = {}
    if case == "different_asset":
        incident.asset.customer_name = "Alupar"
    session = AsyncMock()
    session.__aenter__.return_value = session
    result = MagicMock()
    result.scalar_one_or_none.return_value = None if case == "missing" else incident
    session.execute.return_value = result
    monkeypatch.setattr(ai_context, "SessionLocal", lambda: session)
    if case != "valid":
        with pytest.raises(ValueError):
            await ai_context.trusted_postmortem_context(
                "fp", "8" if case == "wrong_ticket" else "7"
            )
    else:
        context = await ai_context.trusted_postmortem_context("fp", "7")
        assert context["host_id"] == "10882" and context["customer_name"] == "Cavan"
        assert "tags" not in context


def test_embedding_uses_header_and_redacts_input(monkeypatch, caplog):
    monkeypatch.setattr(gemini.settings, "gemini_api_key", "synthetic-key")

    def handler(request):
        assert "synthetic-key" not in str(request.url)
        assert request.headers["x-goog-api-key"] == "synthetic-key"
        assert "synthetic-password" not in request.content.decode()
        return httpx.Response(429)

    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    assert gemini.generate_embedding("password=synthetic-password") == [0.0] * 768
    assert "synthetic-key" not in caplog.text


def test_missing_log_source_does_not_invent_evidence():
    assert postmortem._fetch_related_logs("10882", "9") == []
