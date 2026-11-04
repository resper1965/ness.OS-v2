"""Validate the synthetic signal-v1 examples by hand (stdlib only; jsonschema is optional).

Checks what the contract makes mandatory: envelope fields, timezone-aware instants,
ot.batch fields and digest, batch only on ot.batch, and that the schema file lists the
same required fields.

Digest limitation: the contract says RFC 8785 (JCS). There is no stdlib JCS, so
jcs() uses json.dumps(sort_keys, compact separators, ensure_ascii=False), which is
byte-identical to JCS only when the payload has no floats and no non-BMP characters in
object keys (JCS sorts keys by UTF-16 code units, Python by code points). The synthetic
examples keep integers and strings only; test_jcs_guard rejects anything else.
"""

import hashlib
import json
import re
import unittest
from datetime import datetime
from pathlib import Path

SPECS = Path(__file__).resolve().parents[2] / "docs/specs"
EXAMPLES = sorted((SPECS / "examples/signal-v1").glob("*.json"))
ENVELOPE = (
    "schema_version",
    "source_id",
    "tenant_id",
    "signal_type",
    "occurred_at",
    "collected_at",
    "received_at",
    "severity_source",
    "payload",
)
INSTANT = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)


def jcs(value):
    """RFC 8785 bytes for the subset the examples use (see module docstring)."""

    def check(node):
        if isinstance(node, float):
            raise AssertionError("float needs a real JCS implementation")
        if isinstance(node, dict):
            for k, v in node.items():
                if any(ord(c) > 0xFFFF for c in k):
                    raise AssertionError("non-BMP key needs a real JCS implementation")
                check(v)
        elif isinstance(node, list):
            for v in node:
                check(v)

    check(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def instant(value):
    """Parse an RFC 3339 instant; reject anything without an explicit offset."""
    assert isinstance(value, str) and INSTANT.match(value), f"bad instant: {value!r}"
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert dt.utcoffset() is not None, f"naive instant: {value!r}"
    return dt


class SignalV1Test(unittest.TestCase):
    def test_examples_cover_wazuh_cloud_ot(self):
        kinds = {p.name.split("-")[0] for p in EXAMPLES}
        self.assertTrue({"wazuh", "cloud", "ot"} <= kinds, kinds)

    def test_schema_requires_the_envelope(self):
        schema = json.loads((SPECS / "signal-contract-v1.schema.json").read_text())
        self.assertEqual(set(schema["required"]), set(ENVELOPE))
        self.assertNotIn("links", schema["required"])

    def test_examples(self):
        for path in EXAMPLES:
            with self.subTest(path.name):
                doc = json.loads(path.read_text())
                for key in ENVELOPE:
                    self.assertIn(key, doc)
                self.assertRegex(doc["schema_version"], r"^1\.\d+$")
                self.assertTrue(doc["source_id"])
                self.assertTrue(doc["tenant_id"] is None or doc["tenant_id"])
                self.assertIsInstance(doc["payload"], dict)
                sev = doc["severity_source"]
                self.assertTrue(sev["scheme"] and "value" in sev)
                for key in ("occurred_at", "collected_at", "received_at"):
                    instant(doc[key])
                if doc["signal_type"] == "ot.batch":
                    self.check_batch(doc)

    def check_batch(self, doc):
        batch = doc["batch"]
        for key in ("batch_id", "rules_version", "interval", "integrity"):
            self.assertTrue(batch[key])
        self.assertLess(
            instant(batch["interval"]["start"]), instant(batch["interval"]["end"])
        )
        integrity = batch["integrity"]
        self.assertEqual(integrity["algorithm"], "sha256")
        self.assertEqual(integrity["digest"], hashlib.sha256(jcs(doc["payload"])).hexdigest())
        events = doc["payload"].get("events")
        if "event_count" in integrity and isinstance(events, list):
            self.assertEqual(integrity["event_count"], len(events))

    def test_batch_only_on_ot_batch(self):
        for path in EXAMPLES:
            doc = json.loads(path.read_text())
            self.assertEqual(
                "batch" in doc, doc["signal_type"] == "ot.batch", path.name
            )

    def test_schema_forbids_batch_outside_ot(self):
        schema = json.loads((SPECS / "signal-contract-v1.schema.json").read_text())
        self.assertEqual(schema["then"], {"required": ["batch"]})
        self.assertEqual(schema["else"], {"not": {"required": ["batch"]}})

    def test_cloud_event_with_batch_is_rejected(self):
        ot = json.loads((SPECS / "examples/signal-v1/ot-batch.json").read_text())
        bad = json.loads((SPECS / "examples/signal-v1/cloud-event.json").read_text())
        bad["batch"] = ot["batch"]
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed; structure checked above")
        schema = json.loads((SPECS / "signal-contract-v1.schema.json").read_text())
        validator = jsonschema.Draft202012Validator(schema)
        self.assertTrue(list(validator.iter_errors(bad)))
        self.assertFalse(list(validator.iter_errors(ot)))

    def test_ot_without_event_count_or_events(self):
        doc = json.loads((SPECS / "examples/signal-v1/ot-batch.json").read_text())
        del doc["batch"]["integrity"]["event_count"]
        self.check_batch(doc)
        doc["payload"] = {"raw": "sintetico"}
        doc["batch"]["integrity"]["digest"] = hashlib.sha256(jcs(doc["payload"])).hexdigest()
        doc["batch"]["integrity"]["event_count"] = 99  # no events list: not compared
        self.check_batch(doc)

    def test_jcs_guard(self):
        self.assertEqual(jcs({"b": 1, "a": "é"}), '{"a":"é","b":1}'.encode("utf-8"))
        with self.assertRaises(AssertionError):
            jcs({"v": 1.0})

    def test_naive_instant_is_rejected(self):
        for bad in ("2026-11-04T10:00:00", "2026-11-04", "", None):
            with self.assertRaises(AssertionError):
                instant(bad)


if __name__ == "__main__":
    unittest.main()
