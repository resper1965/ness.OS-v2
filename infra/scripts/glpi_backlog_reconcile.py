"""Read-only, bounded GLPI marker reconciliation for unaudited Hub incidents.

Run inside the Hub API runtime with PYTHONPATH including app/backend and repo root.
Never outputs fingerprints, ticket IDs, tenant names, or API errors.
"""

import argparse
import asyncio
import json
from collections import Counter


async def reconcile_page(rows, glpi, after_id):
    from app.workers.alerts import resolve_glpi_entity_id

    counts = Counter()
    retry_page = False
    for row in rows:
        try:
            if not row["customer"]:
                raise ValueError("No verified customer")
            entity_id = resolve_glpi_entity_id(row["customer"])
        except ValueError:
            counts["entity_unmapped"] += 1
            retry_page = True
            continue
        try:
            await glpi.change_active_entity(entity_id)
            ticket_id = await glpi.find_ticket_by_name_marker(
                f"[n.infraops:{row['fingerprint']}]", entity_id
            )
            counts["remote_found" if ticket_id else "remote_absent"] += 1
        except Exception:  # noqa: BLE001 - fail closed without exposing GLPI response
            counts["lookup_failed"] += 1
            retry_page = True
    return {
        "scanned": len(rows),
        "counts": dict(sorted(counts.items())),
        "next_cursor": (
            after_id if retry_page else (rows[-1]["id"] if rows else after_id)
        ),
    }


async def report(after_id, limit):
    from app.database import SessionLocal
    from app.integrations.glpi import GLPIClient
    from sqlalchemy import text

    query = text("""
        SELECT i.id, i.fingerprint,
               i.tags ->> 'ninf_customer_name' AS customer
        FROM n_infraops_incidents i
        WHERE i.deskmanager_ticket_id IS NULL
          AND i.tags ? 'ninf_zabbix_event_id'
          AND i.id > :after_id
          AND NOT EXISTS (
              SELECT 1 FROM n_infraops_incident_actions a
              WHERE a.incident_id = i.id
          )
        ORDER BY i.id LIMIT :limit
    """)
    async with SessionLocal() as session, session.begin():
        await session.execute(text("SET TRANSACTION READ ONLY"))
        rows = (
            (await session.execute(query, {"after_id": after_id, "limit": limit}))
            .mappings()
            .all()
        )

    glpi = GLPIClient()
    try:
        await glpi.init_session()
        result = await reconcile_page(rows, glpi, after_id)
    finally:
        await glpi.kill_session()
    return {
        "mode": "read_only_aggregate",
        **result,
        "more_possible": len(rows) == limit,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after-id", type=int, default=0)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    if args.after_id < 0 or not 1 <= args.limit <= 5:
        parser.error("after-id must be nonnegative and limit must be 1..5")
    try:
        print(
            json.dumps(asyncio.run(report(args.after_id, args.limit)), sort_keys=True)
        )
    except Exception:  # noqa: BLE001 - never print credentials or remote error bodies
        print(json.dumps({"status": "reconciliation_failed"}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
