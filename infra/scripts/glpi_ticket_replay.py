"""Re-enqueue open incidents that never got a GLPI ticket. Dry-run unless --go.

Run inside the API container, script via stdin:
  docker exec -i ninf-api python - [--go] --ids 1,2,3 < infra/scripts/glpi_ticket_replay.py
Prints only incident id and title.
"""

import argparse
import asyncio
import sys


def replay(rows, payload_cls, fingerprint, enqueue, go):
    """Return (id, title, enqueued) for rows whose rebuilt payload matches the stored fingerprint."""
    out = []
    for r in rows:
        tags = r.tags or {}
        payload = payload_cls(
            event_id=tags.get("ninf_zabbix_event_id"),
            host_id=r.host_id,
            host_name=r.host_name,
            trigger_id=r.trigger_id,
            trigger_name=r.title,
            severity=r.severity,
            status="PROBLEM",
            tags={k: v for k, v in tags.items() if not k.startswith("ninf_")},
        )
        fp = fingerprint(payload)
        if fp != r.fingerprint:
            continue
        if go:
            enqueue(payload.model_dump(mode="json"), fp)
        out.append((r.id, r.title, go))
    return out


async def _load(ids):
    from app.database import SessionLocal
    from sqlalchemy import text

    async with SessionLocal() as s:
        async with s.begin():
            await s.execute(text("SET TRANSACTION READ ONLY"))
            return (
                await s.execute(
                    text(
                        "SELECT id,fingerprint,host_id,host_name,trigger_id,title,severity,tags"
                        " FROM n_infraops_incidents WHERE id = ANY(:ids)"
                        " AND deskmanager_ticket_id IS NULL AND status='open'"
                    ),
                    {"ids": ids},
                )
            ).all()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--ids", required=True)
    args = ap.parse_args(argv)
    from app.core.fingerprint import generate_event_fingerprint
    from app.models.schemas import ZabbixAlertPayload
    from app.workers.alerts import process_alert_v1

    rows = asyncio.run(_load([int(i) for i in args.ids.split(",") if i]))
    enqueue = lambda p, fp: process_alert_v1.apply_async(
        args=[p, fp], queue="alerts.primary"
    )
    for i, title, sent in replay(
        rows, ZabbixAlertPayload, generate_event_fingerprint, enqueue, args.go
    ):
        print("ENQ" if sent else "DRY", i, title[:80])


if __name__ == "__main__":
    main(sys.argv[1:])
