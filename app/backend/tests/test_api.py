# -------------------------------------------------------
# n.infraops — Testes de Integração da API Webhook
# -------------------------------------------------------
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_redis


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


@patch("app.api.webhooks.try_acquire_lock")
@patch("app.api.webhooks.process_alert")
def test_webhook_zabbix_primary(mock_process_alert, mock_try_acquire, client):
    # Simula lock adquirido
    mock_try_acquire.return_value = True

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

    response = client.post("/webhook/zabbix", json=payload)
    assert response.status_code == 202
    assert response.json()["accepted"] is True
    assert response.json()["queue"] == "primary"

    # Verifica se a task Celery correspondente foi agendada
    mock_process_alert.apply_async.assert_called_once()
    args, kwargs = mock_process_alert.apply_async.call_args
    assert kwargs["queue"] == "alerts.primary"


@patch("app.api.webhooks.try_acquire_lock")
@patch("app.api.webhooks.process_deferred_alert")
def test_webhook_zabbix_deferred(mock_process_deferred, mock_try_acquire, client):
    # Simula lock falhado (já existe outro worker processando)
    mock_try_acquire.return_value = False

    payload = {
        "event_id": "1002",
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

    response = client.post("/webhook/zabbix", json=payload)
    assert response.status_code == 202
    assert response.json()["accepted"] is True
    assert response.json()["queue"] == "deferred"

    # Verifica se a task deferred Celery foi agendada com countdown (delay)
    mock_process_deferred.apply_async.assert_called_once()
    args, kwargs = mock_process_deferred.apply_async.call_args
    assert kwargs["queue"] == "alerts.deferred"
    assert kwargs["countdown"] == 2  # default lock_retry_delay_seconds
