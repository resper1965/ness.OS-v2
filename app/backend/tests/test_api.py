# -------------------------------------------------------
# n.infraops — Testes de Integração da API Webhook
# -------------------------------------------------------
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_redis
from app.main import app


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def client(mock_redis, monkeypatch):
    from app.api.webhooks import settings

    monkeypatch.setattr(settings, "webhook_api_key", "test-webhook-key")
    # Sobrescreve dependência do Redis para usar o mock
    app.dependency_overrides[get_redis] = lambda: mock_redis
    with TestClient(app, headers={"X-Api-Key": "test-webhook-key"}) as c:
        yield c
    app.dependency_overrides.clear()


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "n.infraops"
    assert response.json()["status"] == "running"


def test_health_endpoint(client, mock_redis):
    response = client.get("/webhook/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "webhook-receiver"}
    mock_redis.ping.assert_called_once()


@patch("app.api.v1.alerts.process_alert_v1")
@patch("app.api.webhooks.process_alert_v1")
def test_zabbix_entrypoints_share_event_fingerprint_and_worker(
    webhook_task, v1_task, client
):
    payload = {
        "event_id": "1001",
        "host_id": "10001",
        "host_name": "web-server-01",
        "host_ip": "192.168.1.10",
        "trigger_id": "20002",
        "trigger_name": "CPU usage is high",
        "trigger_description": "CPU warning threshold",
        "severity": 4,
        "status": "PROBLEM",
        "timestamp": "2026-06-30T13:00:00Z",
        "tags": {"env": "prod"},
    }

    webhook = client.post("/webhook/zabbix", json=payload)
    v1 = client.post("/v1/alerts", json=payload)
    replay = client.post("/webhook/zabbix", json=payload)
    next_event = client.post("/webhook/zabbix", json={**payload, "event_id": "1002"})

    assert all(
        response.status_code == 202 for response in (webhook, v1, replay, next_event)
    )
    assert webhook.json()["fingerprint"] == v1.json()["fingerprint"]
    assert webhook.json()["fingerprint"] == replay.json()["fingerprint"]
    assert webhook.json()["fingerprint"] != next_event.json()["fingerprint"]
    assert all(
        response.json()["queue"] == "primary"
        for response in (webhook, v1, replay, next_event)
    )
    assert webhook_task.apply_async.call_count == 3
    v1_task.apply_async.assert_called_once()
    assert (
        v1_task.apply_async.call_args.kwargs["args"][1] == webhook.json()["fingerprint"]
    )
    for call in webhook_task.apply_async.call_args_list:
        assert call.kwargs["queue"] == "alerts.primary"
        assert call.kwargs["args"][1] in {
            webhook.json()["fingerprint"],
            next_event.json()["fingerprint"],
        }
