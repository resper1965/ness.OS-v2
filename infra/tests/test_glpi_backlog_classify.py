from datetime import datetime, timezone

from infra.scripts.glpi_backlog_classify import classify


def test_recent_failure_is_not_mistaken_for_confirmed_retry():
    now = datetime(2026, 10, 13, 3, 0, tzinfo=timezone.utc)
    assert classify("open", now, "100", "ticket_failed", "error=GLPITransientError", now) == "transient_failed_queue_unverified"


def test_missing_source_and_inconsistent_audit_are_not_replay_eligible():
    now = datetime(2026, 10, 13, 3, 0, tzinfo=timezone.utc)
    assert classify("open", now, None, "ticket_failed", "error=GLPITransientError", now) == "source_id_missing"
    assert classify("open", now, "100", "ticket_created", "ticket=10 entity=1", now) == "inconsistent_ticket_audit"


def test_permission_and_old_unknown_have_distinct_reasons():
    now = datetime(2026, 10, 13, 3, 0, tzinfo=timezone.utc)
    old = datetime(2026, 10, 12, 1, 0, tzinfo=timezone.utc)
    assert classify("open", old, "100", "ticket_failed", "error=GLPIPermanentError", now) == "permission_blocked"
    assert classify("open", old, "100", None, None, now) == "historical_unclassified"
    assert classify("open", old, "100", "ticket_retry_exhausted", "retries=12", now) == "retry_exhausted"
