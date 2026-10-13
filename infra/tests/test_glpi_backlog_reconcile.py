import asyncio

from infra.scripts.glpi_backlog_reconcile import reconcile_page


class FakeGLPI:
    def __init__(self):
        self.entity = None

    async def change_active_entity(self, entity_id):
        self.entity = entity_id

    async def find_ticket_by_name_marker(self, marker, entity_id):
        assert entity_id == self.entity
        if marker == "[n.infraops:existing]":
            return 75426
        if marker == "[n.infraops:unavailable]":
            raise RuntimeError("synthetic secret must not appear")
        return None


def test_reconcile_reports_remote_found_without_exposing_identifiers():
    rows = [
        {"id": 10, "fingerprint": "existing", "customer": "Cavan"},
        {"id": 11, "fingerprint": "missing", "customer": "Cavan"},
    ]
    report = asyncio.run(reconcile_page(rows, FakeGLPI(), after_id=9))
    assert report == {
        "scanned": 2,
        "counts": {"remote_found": 1, "remote_absent": 1},
        "next_cursor": 11,
    }
    assert "existing" not in str(report)
    assert "75426" not in str(report)


def test_lookup_error_keeps_cursor_for_retry_without_leaking_exception():
    rows = [{"id": 11, "fingerprint": "unavailable", "customer": "Cavan"}]
    report = asyncio.run(reconcile_page(rows, FakeGLPI(), after_id=9))
    assert report == {
        "scanned": 1,
        "counts": {"lookup_failed": 1},
        "next_cursor": 9,
    }
    assert "synthetic secret" not in str(report)


def test_unmapped_customer_is_not_treated_as_absent_ticket():
    rows = [{"id": 12, "fingerprint": "missing", "customer": None}]
    report = asyncio.run(reconcile_page(rows, FakeGLPI(), after_id=9))
    assert report == {
        "scanned": 1,
        "counts": {"entity_unmapped": 1},
        "next_cursor": 9,
    }
