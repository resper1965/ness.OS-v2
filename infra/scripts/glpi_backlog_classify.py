"""Classify a bounded page of missing GLPI tickets without writing or exposing IDs.

Run inside the Hub API runtime with PYTHONPATH including app/backend and the repo
root. The output is aggregated; a cursor permits deliberate follow-up pages.
"""

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os


def classify(status, created_at, source_event_id, action, note, now):
    """A DB-only view cannot prove Celery has a retry scheduled."""
    if not source_event_id:
        return "source_id_missing"
    if status not in {"open", "acknowledged"}:
        return "non_open_without_ticket"
    if action in {"ticket_created", "ticket_reused"}:
        return "inconsistent_ticket_audit"
    if action == "ticket_retry_exhausted":
        return "retry_exhausted"
    if action == "ticket_failed":
        if note and note.startswith("error=GLPIPermanentError"):
            return "permission_blocked"
        if note and note.startswith("error=GLPITransientError"):
            return "transient_failed_queue_unverified"
        return "failed_unclassified"
    if created_at >= now - timedelta(minutes=10):
        return "recent_unconfirmed"
    return "historical_unclassified"


async def report(after_id: int, limit: int) -> dict:
    from sqlalchemy import text

    from app.database import SessionLocal

    query = text("""
        SELECT i.id, i.status, i.created_at,
               i.tags ->> 'ninf_zabbix_event_id' AS source_event_id,
               last_action.action, last_action.note
        FROM n_infraops_incidents AS i
        LEFT JOIN LATERAL (
            SELECT a.action, a.note
            FROM n_infraops_incident_actions AS a
            WHERE a.incident_id = i.id AND a.actor_source = 'glpi'
            ORDER BY a.id DESC LIMIT 1
        ) AS last_action ON true
        WHERE i.deskmanager_ticket_id IS NULL AND i.id > :after_id
        ORDER BY i.id
        LIMIT :limit
    """)
    async with SessionLocal() as session:
        async with session.begin():
            await session.execute(text("SET TRANSACTION READ ONLY"))
            rows = (await session.execute(query, {"after_id": after_id, "limit": limit})).mappings().all()

    now = datetime.now(timezone.utc)
    counts = Counter(
        classify(row["status"], row["created_at"], row["source_event_id"],
                 row["action"], row["note"], now)
        for row in rows
    )
    return {
        "generated_at_utc": now.isoformat(),
        "mode": "read_only_aggregate",
        "scanned": len(rows),
        "counts": dict(sorted(counts.items())),
        "next_cursor": rows[-1]["id"] if rows else after_id,
        "more_possible": len(rows) == limit,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after-id", type=int, default=0)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.after_id < 0 or not 1 <= args.limit <= 500:
        parser.error("after-id must be nonnegative and limit must be 1..500")
    if not os.environ.get("NINF_DATABASE_URL"):
        parser.error("NINF_DATABASE_URL must be set in the Hub runtime")
    try:
        print(json.dumps(asyncio.run(report(args.after_id, args.limit)), sort_keys=True))
    except Exception:
        print(json.dumps({"status": "classification_failed"}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
