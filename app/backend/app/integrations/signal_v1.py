"""Wazuh alert (as received by /secops/triage) -> signal contract v1 INPUT document.

Pure function, no I/O. Contract: docs/specs/signal-contract-v1.md.
ponytail: /secops/triage does not call this yet; it will in the cut that turns on
the v1 producer, which must pass the real collection instant as collected_at
(never received_at: the Hub derives the delay from their difference). Idempotency is (source_id, event_id): source_id must identify each
Wazuh manager (ids from different managers collide). links/extensions/quality are omitted (optional in the contract).
"""

import math
from datetime import datetime
from typing import Any

from app.integrations.soc_agent import SignalRejected


def _aware(value: Any, field: str) -> str:
    """RFC 3339 instant with explicit offset; never assumes a zone."""
    try:
        # py3.12 fromisoformat accepts Wazuh's '-0300' (no colon) and 'Z'
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise SignalRejected(field, value) from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise SignalRejected(field, value)
    return dt.isoformat()


def wazuh_alert_to_signal_v1(
    payload: dict[str, Any],
    *,
    source_id: str,
    collected_at: datetime,
    received_at: datetime,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SignalRejected("payload", payload)
    raw_rule, raw_agent = payload.get("rule"), payload.get("agent")
    rule: dict[str, Any] = raw_rule if isinstance(raw_rule, dict) else {}
    agent: dict[str, Any] = raw_agent if isinstance(raw_agent, dict) else {}
    occurred = _aware(payload.get("timestamp"), "timestamp")

    # same identity as _dedup_key: Wazuh id, else agent:rule:timestamp
    event_id = payload.get("id")
    if not event_id and agent.get("id") and rule.get("id"):
        event_id = f"{agent['id']}:{rule['id']}:{payload['timestamp']}"

    level = rule.get("level", payload.get("level", payload.get("rule_level")))
    try:
        numeric = (
            isinstance(level, int | float)
            and not isinstance(level, bool)
            and math.isfinite(level)
        )
    except OverflowError:  # int too large for float, e.g. 10**400
        numeric = False

    doc: dict[str, Any] = {
        "schema_version": "1.0",
        "source_id": source_id,
        "tenant_id": None,  # resolved by the Hub, never by the source
        "signal_type": "wazuh.alert",
        "occurred_at": occurred,
        "collected_at": _aware(collected_at, "collected_at"),
        "received_at": _aware(received_at, "received_at"),
        "severity_source": {
            "scheme": "wazuh.level",
            "value": level if numeric else None,
        },
        "payload": payload,
    }
    if event_id:
        doc["event_id"] = str(event_id)
    return doc
