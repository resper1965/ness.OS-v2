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
        env = schema["$defs"]["envelope"]
        # stored record (root) = envelope + tenant_id; input = envelope with tenant_id null/absent
        self.assertEqual(set(schema["required"]) | set(env["required"]), set(ENVELOPE))
        self.assertNotIn("tenant_id", env["required"])
        self.assertNotIn("links", env["required"])
        self.assertEqual(schema["$defs"]["input"]["properties"]["tenant_id"], {"type": "null"})
        self.assertEqual(env["properties"]["severity_source"]["required"], ["scheme"])

    def test_input_examples_have_null_tenant_and_stored_ones_do_not(self):
        for path in EXAMPLES:
            doc = json.loads(path.read_text())
            self.assertEqual(
                doc["tenant_id"] is not None, path.stem.endswith("-stored"), path.name
            )

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
                self.assertTrue(sev["scheme"])
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
        env = schema["$defs"]["envelope"]
        self.assertEqual(env["then"], {"required": ["batch"]})
        self.assertEqual(env["else"], {"not": {"required": ["batch"]}})

    def test_schema_validators(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed; structure checked above")
        schema = json.loads((SPECS / "signal-contract-v1.schema.json").read_text())
        stored = jsonschema.Draft202012Validator(schema)
        entry = jsonschema.Draft202012Validator(
            {**schema, "$ref": "#/$defs/input", "required": []}
        )
        load = lambda n: json.loads((SPECS / f"examples/signal-v1/{n}.json").read_text())
        for path in EXAMPLES:
            doc = json.loads(path.read_text())
            validator = stored if path.stem.endswith("-stored") else entry
            self.assertFalse(list(validator.iter_errors(doc)), path.name)
            self.assertFalse(list(stored.iter_errors(doc)), path.name)
        # tenant_id filled on input is rejected; absent is fine; stored needs the key
        doc = load("cloud-event")
        doc["tenant_id"] = "t1"
        self.assertTrue(list(entry.iter_errors(doc)))
        del doc["tenant_id"]
        self.assertFalse(list(entry.iter_errors(doc)))
        self.assertTrue(list(stored.iter_errors(doc)))
        # severity_source.value absent or null does not discard the signal
        for sev in ({"scheme": "provider"}, {"scheme": "provider", "value": None}):
            doc = load("cloud-event")
            doc["severity_source"] = sev
            self.assertFalse(list(entry.iter_errors(doc)))
        # batch outside ot.batch is rejected
        bad = load("cloud-event")
        bad["batch"] = load("ot-batch")["batch"]
        self.assertTrue(list(entry.iter_errors(bad)))
        # v1.0 accepts 1.1 (unknown field), rejects 2.0
        doc = load("cloud-event")
        doc.update(schema_version="1.1", campo_novo=1)
        self.assertFalse(list(entry.iter_errors(doc)))
        doc["schema_version"] = "2.0"
        self.assertTrue(list(entry.iter_errors(doc)))

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
