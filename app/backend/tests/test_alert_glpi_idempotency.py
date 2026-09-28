import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ml.analyzer import AIAnalysisResult
from app.models import Incident, IncidentAction
from app.workers import alerts
from app.workers.alerts import ensure_glpi_ticket


@pytest.mark.asyncio
async def test_existing_marker_reuses_ticket_without_external_writes():
    glpi = AsyncMock()
    glpi.find_ticket_by_name_marker.return_value = 123

    ticket_id, created = await ensure_glpi_ticket(
        glpi,
        fingerprint="a" * 64,
        entity_id=8,
        category_id=1,
        title="[AIOps] Teste sintético",
        content="conteúdo",
    )

    assert (ticket_id, created) == (123, False)
    glpi.create_ticket.assert_not_awaited()
    glpi.add_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_absent_marker_creates_one_ticket_with_deterministic_key():
    glpi = AsyncMock()
    glpi.find_ticket_by_name_marker.return_value = None
    glpi.create_ticket.return_value = {"id": 456}

    ticket_id, created = await ensure_glpi_ticket(
        glpi,
        fingerprint="b" * 64,
        entity_id=8,
        category_id=1,
        title="[AIOps] Teste sintético",
        content="conteúdo",
    )

    assert (ticket_id, created) == (456, True)
    glpi.create_ticket.assert_awaited_once_with(
        title=f"[n.infraops:{'b' * 64}] [AIOps] Teste sintético",
        content="conteúdo",
        entity_id=8,
        itilcategories_id=1,
    )
    glpi.add_comment.assert_awaited_once_with(
        ticket_id=456,
        content="Chamado gerado automaticamente pela plataforma n.infraops AIOps.",
        private=True,
    )


@pytest.mark.asyncio
async def test_retry_after_comment_failure_reuses_created_ticket():
    glpi = AsyncMock()
    glpi.find_ticket_by_name_marker.side_effect = [None, 456]
    glpi.create_ticket.return_value = {"id": 456}
    glpi.add_comment.side_effect = RuntimeError("followup unavailable")
    kwargs = dict(
        fingerprint="b" * 64,
        entity_id=8,
        category_id=1,
        title="Synthetic",
        content="Synthetic",
    )

    with pytest.raises(RuntimeError, match="followup unavailable"):
        await ensure_glpi_ticket(glpi, **kwargs)

    assert await ensure_glpi_ticket(glpi, **kwargs) == (456, False)
    glpi.create_ticket.assert_awaited_once()
    glpi.add_comment.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_ticket_lookup_never_creates_a_ticket():
    glpi = AsyncMock()
    glpi.find_ticket_by_name_marker.side_effect = RuntimeError("lookup unavailable")

    with pytest.raises(RuntimeError, match="lookup unavailable"):
        await ensure_glpi_ticket(
            glpi,
            fingerprint="c" * 64,
            entity_id=8,
            category_id=1,
            title="Synthetic",
            content="Synthetic",
        )

    glpi.create_ticket.assert_not_awaited()


def test_success_keeps_inhibition_until_expiry(monkeypatch):
    redis = MagicMock()
    redis.set.return_value = True
    process = AsyncMock(return_value={"ticket_id": 123})
    monkeypatch.setattr(alerts, "_get_sync_redis", lambda: redis)
    monkeypatch.setattr(alerts, "_async_process_alert_v1", process)

    assert alerts.process_alert_v1.run({}, "fingerprint") == {"ticket_id": 123}

    process.assert_awaited_once_with({}, "fingerprint")
    redis.eval.assert_not_called()
    redis.delete.assert_not_called()
    redis.close.assert_called_once()


def test_redis_unavailable_retries_without_processing(monkeypatch):
    redis = MagicMock()
    failure = RuntimeError("Redis unavailable")
    redis.set.side_effect = failure
    process = AsyncMock()
    retry = MagicMock(side_effect=failure)
    monkeypatch.setattr(alerts, "_get_sync_redis", lambda: redis)
    monkeypatch.setattr(alerts, "_async_process_alert_v1", process)
    monkeypatch.setattr(alerts.process_alert_v1, "retry", retry)

    with pytest.raises(RuntimeError, match="Redis unavailable"):
        alerts.process_alert_v1.run({}, "fingerprint")

    process.assert_not_called()
    redis.eval.assert_not_called()
    redis.close.assert_called_once()
    retry.assert_called_once_with(exc=failure)


def test_atomic_inhibition_loser_does_not_process_alert(monkeypatch):
    redis = MagicMock()
    redis.exists.return_value = False
    redis.set.return_value = None  # Another worker acquired the key first.
    process = AsyncMock()
    monkeypatch.setattr(alerts, "_get_sync_redis", lambda: redis)
    monkeypatch.setattr(alerts, "_async_process_alert_v1", process)

    result = alerts.process_alert_v1.run({}, "fingerprint")

    assert result == {"status": "deduplicated", "fingerprint": "fingerprint"}
    process.assert_not_called()
    redis.close.assert_called_once()


def test_processing_failure_releases_only_owned_inhibition_and_retries(monkeypatch):
    redis = MagicMock()
    redis.exists.return_value = False
    redis.set.return_value = True
    failure = RuntimeError("GLPI unavailable")
    process = AsyncMock(side_effect=failure)
    retry = MagicMock(side_effect=failure)
    monkeypatch.setattr(alerts, "_get_sync_redis", lambda: redis)
    monkeypatch.setattr(alerts, "_async_process_alert_v1", process)
    monkeypatch.setattr(alerts.process_alert_v1, "retry", retry)

    with pytest.raises(RuntimeError, match="GLPI unavailable"):
        alerts.process_alert_v1.run({}, "fingerprint")

    token = redis.set.call_args.args[1]
    assert isinstance(token, str) and token != "1"
    assert redis.set.call_args.kwargs == {"ex": 300, "nx": True}
    redis.delete.assert_not_called()
    assert redis.eval.call_args.args[1:] == (1, "ninf:inhibit:fingerprint", token)
    retry.assert_called_once_with(exc=failure)


@pytest.mark.asyncio
@pytest.mark.parametrize("glpi_fails", [False, True])
@pytest.mark.parametrize("notifications_enabled", [False, True])
@pytest.mark.parametrize("existing_state", ("new", "unlinked", "linked"))
@pytest.mark.parametrize("ticket_exists", [False, True])
@pytest.mark.parametrize("delivery_failure", [None, "commit", "redis"])
async def test_pipeline_persists_incident_and_retries_glpi_failure(
    monkeypatch,
    glpi_fails,
    notifications_enabled,
    existing_state,
    ticket_exists,
    delivery_failure,
):
    existing = existing_state != "new"
    linked_before = existing_state == "linked"
    glpi = AsyncMock()
    failure = RuntimeError("GLPI unavailable")
    glpi.find_ticket_by_name_marker.side_effect = failure if glpi_fails else None
    glpi.find_ticket_by_name_marker.return_value = 123 if ticket_exists else None
    glpi.create_ticket.return_value = {"id": 123}
    analysis = AIAnalysisResult(
        executive_action_plan="Synthetic",
        technical_action_plan="Synthetic",
        urgency="HIGH",
        isolation_required=False,
        probable_cause="Synthetic",
        recommended_playbook="Synthetic",
    )
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.execute.return_value.scalar_one_or_none.return_value = None
    previous = MagicMock(
        id=3,
        alert_count=1,
        tags={"ninf_zabbix_event_id": ""},
        deskmanager_ticket_id="123" if linked_before else None,
        assigned_user_id=None,
        first_seen=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status="resolved",
    )
    if existing:
        incident_result, asset_result = MagicMock(), MagicMock()
        incident_result.scalar_one_or_none.return_value = previous
        asset_result.scalar_one_or_none.return_value = None
        session.execute.side_effect = [incident_result, asset_result]

    async def flush():
        for call in session.add.call_args_list:
            added = call.args[0]
            if isinstance(added, Incident) and added.id is None:
                added.id = 99

    session.flush = AsyncMock(side_effect=flush)
    committed = []

    @asynccontextmanager
    async def transaction():
        yield
        if delivery_failure == "commit":
            raise RuntimeError("Commit failed")
        committed.append(True)

    @asynccontextmanager
    async def session_factory():
        yield session

    session.begin.side_effect = transaction
    whatsapp = AsyncMock()
    push = AsyncMock()
    monkeypatch.setattr(alerts, "GLPIClient", lambda: glpi)
    monkeypatch.setattr(alerts, "analyze_incident", AsyncMock(return_value=analysis))
    monkeypatch.setattr(alerts, "lookup_glpi_asset", AsyncMock(return_value=None))
    monkeypatch.setattr(alerts, "SessionLocal", session_factory)
    redis = MagicMock()
    published = []

    def publish(channel, body):
        published.append((list(committed), channel, json.loads(body)))
        if delivery_failure == "redis":
            raise RuntimeError("Redis unavailable")

    redis.publish.side_effect = publish
    monkeypatch.setattr(alerts, "_get_sync_redis", lambda: redis)
    monkeypatch.setattr(alerts, "LokiClient", lambda: AsyncMock())
    monkeypatch.setattr(alerts, "WhatsAppClient", lambda: whatsapp)
    monkeypatch.setattr(alerts.settings, "whatsapp_noc_group_id", "synthetic")
    monkeypatch.setattr(
        alerts.settings, "alert_notifications_enabled", notifications_enabled
    )
    monkeypatch.setattr("app.integrations.webpush.notify_tenant_stakeholders", push)

    alert_data = {"host_name": "CAVAN-test", "severity": 4}
    if delivery_failure == "commit":
        with pytest.raises(RuntimeError, match="Commit failed"):
            await alerts._async_process_alert_v1(alert_data, "a" * 64)
        redis.publish.assert_not_called()
        assert not committed
        return
    elif glpi_fails:
        with pytest.raises(RuntimeError, match="GLPI unavailable"):
            await alerts._async_process_alert_v1(alert_data, "a" * 64)
    else:
        result = await alerts._async_process_alert_v1(alert_data, "a" * 64)
        assert result["ticket_id"] == 123
        assert result["whatsapp_sent"] is notifications_enabled

    assert committed == [True]
    redis.publish.assert_called_once()
    redis.close.assert_called_once()
    commit_at_publish, channel, event = published[0]
    assert commit_at_publish == [True]
    assert channel == "ninf_incidents"
    if existing:
        assert event["status"] == "resolved"
        assert event["pipeline_stage"] == "resolved"
        assert event["first_seen"] == previous.first_seen.isoformat()
    added = [call.args[0] for call in session.add.call_args_list]
    incidents = [item for item in added if isinstance(item, Incident)]
    actions = [item for item in added if isinstance(item, IncidentAction)]
    assert len(incidents) == (0 if existing else 1)
    assert [item.action for item in actions] == (
        ([] if existing else ["incident_created"])
        + (
            ["ticket_failed"]
            if glpi_fails
            else []
            if linked_before and ticket_exists
            else ["ticket_reused" if ticket_exists else "ticket_created"]
        )
    )
    if existing:
        assert previous.alert_count == 1
    glpi.kill_session.assert_awaited_once()
    incident = previous if existing else incidents[0]
    assert all(item.incident_id == incident.id for item in actions)
    assert incident.deskmanager_ticket_id == (
        "123" if linked_before or not glpi_fails else None
    )
    glpi.find_ticket_by_name_marker.assert_awaited_once_with(
        f"[n.infraops:{'a' * 64}]", 8
    )
    if glpi_fails or ticket_exists:
        glpi.create_ticket.assert_not_awaited()
    else:
        glpi.create_ticket.assert_awaited_once()
    if glpi_fails or not notifications_enabled:
        whatsapp.send_text_message.assert_not_awaited()
        push.assert_not_called()
    else:
        whatsapp.send_text_message.assert_awaited_once()
        push.assert_called_once()
