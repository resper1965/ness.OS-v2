"""P0 Fundação SOC: validação, modelo assíncrono com prazo, atendimento e chave de frequência."""

import asyncio
import logging

import pytest

from app.api.routers import secops
from app.core.triage_engine import TriageAction
from app.integrations import soc_agent

ALERT = {"id": "sig-1", "rule": {"id": "5", "level": 14}, "agent": {"id": "1"}}


@pytest.mark.parametrize(
    "conf", [float("nan"), float("inf"), -0.1, 1.1, "0.9", None, True]
)
def test_confidence_invalid_is_rejected_with_field_and_value(conf):
    data = {
        "classification": "HIGH",
        "confidence": conf,
        "summary": "s",
        "action_taken": "a",
    }
    with pytest.raises(soc_agent.SignalRejected) as e:
        soc_agent._validated(data)
    assert e.value.field == "confidence"


def test_classification_outside_enum_is_rejected():
    data = {
        "classification": "SEVERE",
        "confidence": 0.5,
        "summary": "s",
        "action_taken": "a",
    }
    with pytest.raises(soc_agent.SignalRejected) as e:
        soc_agent._validated(data)
    assert (e.value.field, e.value.value) == ("classification", "SEVERE")


@pytest.mark.asyncio
async def test_rejection_is_logged_and_signal_keeps_attendance(monkeypatch, caplog):
    monkeypatch.setattr(soc_agent.settings, "llm_api_key", "k")

    async def nan_reply(*a, **k):
        return (
            '{"classification":"HIGH","confidence":NaN,"summary":"s","action_taken":"a"}',
            {},
        )

    monkeypatch.setattr(soc_agent, "achat_completion", nan_reply)
    with caplog.at_level(logging.ERROR):
        out = await soc_agent.triage_wazuh_alert(ALERT, "cavan")
    assert out["action_taken"] == "Criar ticket de triagem manual"
    log = caplog.text
    assert "campo=confidence" in log and "nan" in log.lower() and "sig-1" in log


@pytest.mark.asyncio
async def test_model_timeout_does_not_block_nor_lose_signal(monkeypatch):
    monkeypatch.setattr(soc_agent.settings, "llm_api_key", "k")
    monkeypatch.setattr(soc_agent, "_DEADLINE", 0.05)

    async def hang(*a, **k):
        await asyncio.sleep(5)

    monkeypatch.setattr(soc_agent, "achat_completion", hang)
    out = await asyncio.wait_for(soc_agent.triage_wazuh_alert(ALERT, "cavan"), 2)
    assert out["classification"] == "HIGH" and "TimeoutError" in out["summary"]


@pytest.mark.parametrize("level", [10, 12, 15])
def test_attendance_decision_uses_only_rule_and_score(level):
    # rótulos de teste, não piso: o limiar vem de settings
    got = secops._attendance_required(
        False, TriageAction.ARCHIVE, {"level": level, "level_invalid": False}
    )
    assert got is (level >= secops.settings.soc_attendance_min_level)


def test_pending_and_high_score_always_attend():
    low = {"level": 1, "level_invalid": False}
    assert secops._attendance_required(True, TriageAction.ARCHIVE, low) is True
    assert secops._attendance_required(False, TriageAction.TRIAGE_L1, low) is True
    assert secops._attendance_required(False, TriageAction.ARCHIVE, low) is False


def test_free_text_rejection_is_not_echoed_in_log(monkeypatch, caplog):
    import json

    monkeypatch.setattr(soc_agent.settings, "llm_api_key", "k")

    async def reply(*a, **k):
        bad = {
            "classification": "HIGH",
            "confidence": 0.5,
            "summary": "  ",
            "action_taken": "a",
        }
        return json.dumps(bad), {}

    monkeypatch.setattr(soc_agent, "achat_completion", reply)
    with caplog.at_level(logging.ERROR):
        asyncio.run(soc_agent.triage_wazuh_alert(ALERT, "cavan"))
    assert "campo=summary" in caplog.text and "str len=2" in caplog.text


def test_freq_key_is_scoped_by_tenant_and_cluster():
    p = {"manager": {"name": "m1"}}
    a = secops._freq_key("cavan", p, "001", "100")
    assert a == secops._freq_key("cavan", p, "001", "100")
    assert a != secops._freq_key("unimed", p, "001", "100")
    assert a != secops._freq_key("cavan", {"manager": {"name": "m2"}}, "001", "100")
    assert a != secops._freq_key(None, p, "001", "100")  # pendente não soma com tenant


def test_pending_without_cluster_has_no_frequency_key():
    assert secops._freq_key(None, {}, "001", "100") is None
    assert secops._freq_key(None, {"manager": {"name": "m1"}}, "001", "100")
