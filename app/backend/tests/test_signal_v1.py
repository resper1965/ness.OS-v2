import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.integrations.signal_v1 import wazuh_alert_to_signal_v1
from app.integrations.soc_agent import SignalRejected

SPECS = Path(__file__).resolve().parents[3] / "docs/specs"
SCHEMA = json.loads((SPECS / "signal-contract-v1.schema.json").read_text())
RECV = datetime(2026, 11, 4, 13, 15, 32, tzinfo=UTC)


def _alert(**over):
    a = {
        "id": "1762250130.123456",
        "timestamp": "2026-11-04T10:15:30.123-0300",
        "rule": {"id": "100999", "level": 12},
        "agent": {"id": "001", "name": "host-sintetico-01"},
        "manager": {"name": "wazuh-manager-sintetico-01"},
    }
    a.update(over)
    return a


def _conv(a):
    return wazuh_alert_to_signal_v1(
        a, source_id="wazuh-manager-sintetico-01", received_at=RECV
    )


def test_valid_against_input_schema():
    doc = _conv(_alert())
    schema = {**SCHEMA, "$ref": "#/$defs/input"}
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(doc)
    ex = json.loads((SPECS / "examples/signal-v1/wazuh-alert.json").read_text())
    assert doc["event_id"] == ex["event_id"] == ex["payload"]["id"]
    assert doc["signal_type"] == ex["signal_type"]
    assert doc["severity_source"] == ex["severity_source"]
    assert doc["payload"] is not None and doc["payload"]["id"] == ex["payload"]["id"]


@pytest.mark.parametrize("ts", [None, "", "2026-11-04T10:15:30", "2026-11-04", "x", 5])
def test_timestamp_without_zone_rejected(ts):
    with pytest.raises(SignalRejected) as e:
        _conv(_alert(timestamp=ts))
    assert e.value.field == "timestamp"


def test_naive_received_at_rejected():
    with pytest.raises(SignalRejected):
        wazuh_alert_to_signal_v1(
            _alert(), source_id="s", received_at=datetime(2026, 1, 1)
        )


def test_offset_normalized_same_instant():
    doc = _conv(_alert())
    got = datetime.fromisoformat(doc["occurred_at"])
    assert doc["occurred_at"].endswith("-03:00")
    assert got == datetime(2026, 11, 4, 13, 15, 30, 123000, tzinfo=UTC)


def test_tenant_never_filled():
    for a in (_alert(), _alert(tenant_id="x", rule={"level": 3})):
        assert _conv(a)["tenant_id"] is None


@pytest.mark.parametrize(
    "rule", [{}, {"level": None}, {"level": "abc"}, {"level": True}, {"level": 10**400}]
)
def test_missing_severity_is_null_not_downgraded(rule):
    doc = _conv(_alert(rule=rule))
    assert doc["severity_source"] == {"scheme": "wazuh.level", "value": None}


def test_event_id_deterministic():
    assert _conv(_alert())["event_id"] == _conv(_alert())["event_id"]
    no_id = _alert(id=None)
    assert _conv(no_id)["event_id"] == "001:100999:2026-11-04T10:15:30.123-0300"
    assert "event_id" not in _conv(_alert(id=None, agent={}))
