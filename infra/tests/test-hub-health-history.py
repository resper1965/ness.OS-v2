import importlib.util
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

source = Path(__file__).resolve().parents[1] / "scripts/hub-health-history.py"
spec = importlib.util.spec_from_file_location("history", source)
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 8, 22, 0, tzinfo=timezone.utc)
        self.value = {
            "status": "ok",
            "checked_at": self.now.isoformat(),
            "duration_ms": 12,
        }
        for key in history.COMPONENTS:
            self.value[key] = {"status": "ok", "duration_ms": 10}

    def test_valid_health_is_preserved(self):
        result = history.normalized(json.dumps(self.value), 0, self.now)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["recorded_at"], self.now.isoformat())

    def test_empty_traceback_and_exit_mismatch_are_errors(self):
        for raw, code in [
            ("", 127),
            ("Traceback password=secret", 1),
            (json.dumps(self.value), 124),
        ]:
            with self.subTest(code=code):
                result = history.normalized(raw, code, self.now)
                self.assertEqual(result["status"], "error")
                self.assertNotIn("secret", json.dumps(result))

    def test_old_health_cannot_be_republished_as_current(self):
        result = history.normalized(
            json.dumps(self.value), 0, self.now + timedelta(minutes=3)
        )
        self.assertEqual(result["status"], "error")

    def test_invalid_and_inconsistent_metrics_fail_closed(self):
        for duration in [True, -1, "10", float("nan"), float("inf")]:
            self.value["glpi"]["duration_ms"] = duration
            result = history.normalized(json.dumps(self.value), 0, self.now)
            self.assertEqual(result["status"], "error")
        self.value["glpi"] = {"status": "error", "duration_ms": 10}
        self.assertEqual(
            history.normalized(json.dumps(self.value), 0, self.now)["status"], "error"
        )

    def test_status_history_and_retention(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            old = directory / "health-2026-01-01.jsonl"
            old.write_text("old")
            unrelated = directory / "other-backup.jsonl"
            unrelated.write_text("keep")
            bad_date = directory / "health-2026-99-99.jsonl"
            bad_date.write_text("")
            history.record(directory, json.dumps(self.value), 0, self.now)
            self.assertFalse(old.exists())
            self.assertTrue(unrelated.exists())
            self.assertTrue(bad_date.exists())
            self.assertEqual((directory / "status.json").stat().st_mode & 0o777, 0o600)
            history.record(directory, "", 124, self.now + timedelta(minutes=1))
            result = history.summarize(directory, 24, self.now + timedelta(minutes=2))
            self.assertEqual(result["samples"], 2)
            self.assertEqual(result["unhealthy_sample_percent"], 50)
            self.assertEqual(result["components"]["glpi"]["p95_ms"], 10)
            self.assertEqual(result["components"]["glpi"]["unhealthy_samples"], 1)
            self.assertEqual(
                json.loads((directory / "status.json").read_text())["status"], "error"
            )

    def test_empty_history_does_not_claim_availability(self):
        with tempfile.TemporaryDirectory() as directory:
            result = history.summarize(Path(directory), 24, self.now)
            self.assertIsNone(result["unhealthy_sample_percent"])
            self.assertIsNone(result["components"]["glpi"]["p95_ms"])


if __name__ == "__main__":
    unittest.main()
