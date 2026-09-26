import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.email import (
    EmailDeliveryError,
    EmailDeliveryMetrics,
    EmailDisabledError,
    ResendEmailClient,
)


def _client(handler, **overrides):
    options = {
        "enabled": True,
        "api_key": "test-api-key",
        "sender": "ness.OS Hub <hub@ness.com.br>",
        "transport": httpx.MockTransport(handler),
    }
    options.update(overrides)
    return ResendEmailClient(**options)


@pytest.mark.asyncio
async def test_disabled_gate_blocks_before_network_request():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"id": "unexpected"})

    metrics = EmailDeliveryMetrics()
    client = _client(handler, enabled=False, metrics=metrics)

    with pytest.raises(EmailDisabledError, match="disabled"):
        await client.send(
            to=["operator@example.invalid"],
            subject="Test",
            text="Test body",
            idempotency_key="hub:test:disabled",
        )

    assert calls == 0
    assert metrics.requested == 1
    assert metrics.blocked == 1


@pytest.mark.asyncio
async def test_send_uses_resend_contract_and_returns_provider_id():
    def handler(request):
        assert request.url == "https://api.resend.com/emails"
        assert request.headers["Authorization"] == "Bearer test-api-key"
        assert request.headers["Idempotency-Key"] == "hub:invite:42"
        assert request.headers["Content-Type"] == "application/json"
        assert json.loads(request.content) == {
            "from": "ness.OS Hub <hub@ness.com.br>",
            "to": ["operator@example.invalid"],
            "subject": "Invite",
            "html": "<p>Welcome</p>",
        }
        return httpx.Response(200, json={"id": "email-123"})

    metrics = EmailDeliveryMetrics()
    result = await _client(handler, metrics=metrics).send(
        to=["operator@example.invalid"],
        subject="Invite",
        html="<p>Welcome</p>",
        idempotency_key="hub:invite:42",
    )

    assert result.email_id == "email-123"
    assert result.attempts == 1
    assert metrics.succeeded == 1
    assert metrics.failed == 0


@pytest.mark.asyncio
async def test_retry_reuses_idempotency_key_after_rate_limit():
    keys = []

    def handler(request):
        keys.append(request.headers["Idempotency-Key"])
        if len(keys) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"id": "email-after-retry"})

    metrics = EmailDeliveryMetrics()
    with patch("app.integrations.email.asyncio.sleep", new=AsyncMock()) as sleep:
        result = await _client(handler, metrics=metrics).send(
            to=["operator@example.invalid"],
            subject="Report",
            text="Report ready",
            idempotency_key="hub:report:42:v1",
        )

    assert result.attempts == 2
    assert keys == ["hub:report:42:v1", "hub:report:42:v1"]
    assert metrics.retried == 1
    sleep.assert_awaited_once_with(0.0)


@pytest.mark.asyncio
async def test_non_retryable_error_does_not_expose_provider_body():
    def handler(request):
        return httpx.Response(
            422,
            json={"message": "recipient operator@example.invalid rejected"},
        )

    with pytest.raises(EmailDeliveryError) as error:
        await _client(handler).send(
            to=["operator@example.invalid"],
            subject="Sensitive subject",
            text="Sensitive body",
            idempotency_key="hub:test:rejected",
        )

    message = str(error.value)
    assert "status 422" in message
    assert "operator@example.invalid" not in message
    assert "Sensitive" not in message


def test_rejects_invalid_retry_configuration():
    with pytest.raises(ValueError, match="between 1 and 5"):
        ResendEmailClient(
            enabled=False,
            api_key="",
            sender="",
            max_attempts=6,
        )
