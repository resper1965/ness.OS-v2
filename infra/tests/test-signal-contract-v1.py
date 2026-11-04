"""Validate the synthetic signal-v1 examples by hand (stdlib only, no jsonschema).

Checks what the contract makes mandatory: envelope fields, timezone-aware instants,
ot.batch fields and digest, and that the schema file lists the same required fields.
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
                occurred, collected, received = (
                    instant(doc[k]) for k in ("occurred_at", "collected_at", "received_at")
                )
                self.assertLessEqual(occurred, collected)
                self.assertLessEqual(collected, received)
                if doc["signal_type"] == "ot.batch":
                    self.check_batch(doc)

    def check_batch(self, doc):
        batch = doc["batch"]
        for key in ("batch_id", "rules_version", "interval", "integrity"):
            self.assertTrue(batch[key])
        self.assertLess(
            instant(batch["interval"]["start"]), instant(batch["interval"]["end"])
        )
        canonical = json.dumps(
            doc["payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        integrity = batch["integrity"]
        self.assertEqual(integrity["algorithm"], "sha256")
        self.assertEqual(integrity["digest"], hashlib.sha256(canonical).hexdigest())
        self.assertEqual(integrity["event_count"], len(doc["payload"]["events"]))

    def test_naive_instant_is_rejected(self):
        for bad in ("2026-11-04T10:00:00", "2026-11-04", "", None):
            with self.assertRaises(AssertionError):
                instant(bad)


if __name__ == "__main__":
    unittest.main()
