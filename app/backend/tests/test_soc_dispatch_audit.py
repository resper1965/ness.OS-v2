from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.routers import secops
from app.core.triage_engine import TriageAction
from app.integrations import soc_agent


@pytest.mark.asyncio
@pytest.mark.parametrize("commit_fails", [True, False])
async def test_soc_decision_must_be_persisted(monkeypatch, commit_fails):
    async def resolved(db, payload):
        return "cavan"

    async def no_recent(db, key):
        return 0

    monkeypatch.setattr(secops, "_resolve_tenant", resolved)
    monkeypatch.setattr(secops, "_recent_count", no_recent)
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
        db.rollback.assert_awaited_once()
    else:
        result = await secops.triage_alert(payload, db, SimpleNamespace(id=7))
        assert result["decision_id"] == 19
        assert result["corrective_action_approved"] is False
        audit = db.add.call_args.args[0].raw_alert["_ness_triage_request"]
        assert audit["user_id"] == 7 and audit["corrective_action_approved"] is False
        db.commit.assert_awaited_once()
