from types import SimpleNamespace

from app.integrations import n8n


class Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"ticket_id": "ticket-1"}


def test_n8n_notifications_send_shared_secret_header(monkeypatch):
    key = "k" * 32
    calls = []

    class Client:
        def __init__(self, timeout):
            assert timeout is n8n._TIMEOUT

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def post(self, url, json, headers):
            calls.append((url, json, headers))
            return Response()

    monkeypatch.setattr(n8n.settings, "alert_notifications_enabled", True)
    monkeypatch.setattr(n8n.settings, "n8n_webhook_api_key", key)
    monkeypatch.setattr(n8n.httpx, "Client", Client)
    monkeypatch.setattr(
        n8n,
        "build_incident_payload",
        lambda _: SimpleNamespace(fingerprint="fp-1", model_dump=lambda **_: {}),
    )

    assert (
        n8n.notify_incident_created({"fingerprint": "fp-1"})["ticket_id"] == "ticket-1"
    )
    assert (
        n8n.notify_postmortem_ready(SimpleNamespace(model_dump=lambda **_: {}))[
            "ticket_id"
        ]
        == "ticket-1"
    )
    assert n8n.notify_soc_triage_decision({})["ticket_id"] == "ticket-1"
    assert len(calls) == 3
    assert all(call[2] == {"X-Ness-Webhook-Key": key} for call in calls)


def test_n8n_notifications_fail_closed_without_strong_key(monkeypatch):
    def unexpected_client(*args, **kwargs):
        raise AssertionError("HTTP request must not run without webhook auth")

    monkeypatch.setattr(n8n.settings, "alert_notifications_enabled", True)
    monkeypatch.setattr(n8n.settings, "n8n_webhook_api_key", "short")
    monkeypatch.setattr(n8n.httpx, "Client", unexpected_client)
    monkeypatch.setattr(
        n8n,
        "build_incident_payload",
        lambda _: SimpleNamespace(fingerprint="fp-1", model_dump=lambda **_: {}),
    )

    results = [
        n8n.notify_incident_created({}),
        n8n.notify_postmortem_ready(SimpleNamespace(model_dump=lambda **_: {})),
        n8n.notify_soc_triage_decision({}),
    ]

    assert all(
        result["error"] == "n8n webhook authentication is not configured"
        for result in results
    )
