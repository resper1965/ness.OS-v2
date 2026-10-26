import json
import uuid

import httpx
import pytest

from app.integrations.contabo_firewall import (
    CONTABO_API_URL,
    ContaboFirewallClient,
    ContaboInstanceClient,
)


class TokenManager:
    async def get_token(self) -> str:
        return "test-token"


@pytest.mark.asyncio
async def test_firewall_update_uses_current_contract(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [{"firewallId": "fw-1"}]})

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    rules = [
        {
            "protocol": "tcp",
            "destPorts": '["443"]',
            "srcCidr": {"ipv4": ["AnyIPv4"], "ipv6": []},
            "action": "accept",
            "status": "active",
            "displayName": "HTTPS",
        }
    ]

    await ContaboFirewallClient(TokenManager()).set_firewall_rules(
        "fw-1", rules, "change-123"
    )

    request = requests[0]
    assert request.method == "PUT"
    assert str(request.url) == f"{CONTABO_API_URL}/firewalls/fw-1"
    assert json.loads(request.content) == {"rules": {"inbound": rules}}
    assert request.headers["authorization"] == "Bearer test-token"
    uuid.UUID(request.headers["x-request-id"], version=4)


@pytest.mark.asyncio
async def test_firewall_update_requires_explicit_approval():
    with pytest.raises(ValueError, match="approved_by"):
        await ContaboFirewallClient(TokenManager()).set_firewall_rules("fw-1", [], "")


@pytest.mark.asyncio
async def test_direct_block_is_fail_closed():
    with pytest.raises(NotImplementedError, match="não é suportado"):
        await ContaboFirewallClient(TokenManager()).block_ip(
            "fw-1", "203.0.113.9/32", "change-123"
        )


@pytest.mark.asyncio
async def test_instance_requests_include_request_id():
    headers = await ContaboInstanceClient(TokenManager())._headers()
    assert headers["Authorization"] == "Bearer test-token"
    uuid.UUID(headers["x-request-id"], version=4)
