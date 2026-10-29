from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.routers import secops
from app.core.triage_engine import TriageAction
from app.integrations import n8n, soc_agent


def test_disabled_notifications_do_not_start_any_n8n_workflow(monkeypatch):
    monkeypatch.setattr(n8n.settings, "alert_notifications_enabled", False)
    client = MagicMock(side_effect=AssertionError("External dispatch forbidden"))
    monkeypatch.setattr(n8n.httpx, "Client", client)
    assert n8n.notify_incident_created({})["status"] == "disabled"
    assert n8n.notify_postmortem_ready(None)["status"] == "disabled"
    assert n8n.notify_soc_triage_decision({})["status"] == "disabled"
    client.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("commit_fails", [True, False])
async def test_soc_decision_must_be_persisted_before_dispatch(
    monkeypatch, commit_fails
):
    async def resolved(db, payload):
        return "cavan"

    monkeypatch.setattr(secops, "_resolve_tenant", resolved)
    monkeypatch.setattr(secops, "_extract_ips_and_hashes", lambda payload: ([], []))
    monkeypatch.setattr(
        secops._triage_engine,
        "evaluate_alert",
        lambda **kw: SimpleNamespace(action=TriageAction.TRIAGE_L2, risk_score=90),
    )

    async def triage(payload, tenant):
        return {
            "classification": "HIGH",
            "confidence": 0.8,
            "summary": "Synthetic review",
            "action_taken": "Review required",
        }

    monkeypatch.setattr(soc_agent, "triage_wazuh_alert", triage)
    db = AsyncMock()
    db.add = MagicMock(side_effect=lambda decision: setattr(decision, "id", 19))
    if commit_fails:
        db.commit.side_effect = RuntimeError("private-db-error")
    dispatch = MagicMock(return_value={"status": "disabled"})
    monkeypatch.setattr(n8n, "notify_soc_triage_decision", dispatch)
    payload = {
        "rule": {"id": "1"},
        "agent": {"id": "2", "name": "synthetic", "group": ["cavan"]},
        "_ness_triage_request": {"user_id": 999, "corrective_action_approved": True},
    }
    if commit_fails:
        with pytest.raises(HTTPException) as error:
            await secops.triage_alert(payload, db, SimpleNamespace(id=7))
        assert error.value.status_code == 503
        assert "private-db-error" not in error.value.detail
        dispatch.assert_not_called()
        db.rollback.assert_awaited_once()
    else:
        result = await secops.triage_alert(payload, db, SimpleNamespace(id=7))
        assert result["decision_id"] == 19
        assert result["dispatch_status"] == "disabled"
        assert result["corrective_action_approved"] is False
        audit = db.add.call_args.args[0].raw_alert["_ness_triage_request"]
        assert audit["user_id"] == 7 and audit["corrective_action_approved"] is False
        db.commit.assert_awaited_once()
        dispatch.assert_called_once()
