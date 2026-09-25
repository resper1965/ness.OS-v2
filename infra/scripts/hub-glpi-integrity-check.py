"""Read-only reconciliation of hub rows with a protected GLPI snapshot."""

import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Asset, Incident
from app.workers.alerts import resolve_glpi_entity_id


async def main():
    tickets = json.loads(Path(sys.argv[1]).read_text())["tickets"]
    by_id = {str(t["id"]): t for t in tickets}
    duplicates = [
        fp
        for fp, count in Counter(t["fingerprint"] for t in tickets).items()
        if count > 1
    ]
    findings = [{"reason": "duplicate_marker", "fingerprint": fp} for fp in duplicates]
    async with SessionLocal() as session:
        incidents = (
            await session.scalars(
                select(Incident).where(Incident.tags.has_key("ninf_zabbix_event_id"))
            )
        ).all()
        assets = (
            await session.scalars(
                select(Asset).where(Asset.tags["source"].astext == "zabbix+glpi")
            )
        ).all()
    by_asset = {a.id: a for a in assets}
    checked = 0
    for inc in incidents:
        if not inc.deskmanager_ticket_id:
            findings.append({"incident": inc.id, "reason": "missing_ticket"})
            continue
        ticket = by_id.get(inc.deskmanager_ticket_id)
        if not ticket:
            findings.append({"incident": inc.id, "reason": "ticket_not_in_snapshot"})
            continue
        checked += 1
        expected_entity = resolve_glpi_entity_id(inc.tags["ninf_customer_name"])
        for bad, reason in [
            (ticket["fingerprint"] != inc.fingerprint, "fingerprint_mismatch"),
            (ticket["entity"] != expected_entity, "entity_mismatch"),
            (ticket["deleted"], "ticket_deleted"),
            (not ticket["followups"], "missing_followup"),
        ]:
            if bad:
                findings.append(
                    {"incident": inc.id, "ticket": ticket["id"], "reason": reason}
                )
        asset = by_asset.get(inc.asset_id)
        if asset:
            expected = {
                "itemtype": asset.tags["glpi_itemtype"],
                "id": int(asset.tags["glpi_item_id"]),
            }
            if expected not in ticket["assets"]:
                findings.append(
                    {
                        "incident": inc.id,
                        "ticket": ticket["id"],
                        "reason": "missing_asset_link",
                    }
                )
            if asset.customer_id != inc.tags["ninf_customer_name"].strip().lower():
                findings.append(
                    {"incident": inc.id, "reason": "asset_customer_mismatch"}
                )
        elif inc.host_id != "10978":
            findings.append({"incident": inc.id, "reason": "missing_cmdb_asset"})
    missing_owners = [a.id for a in assets if not a.tags.get("owner")]
    findings.extend({"asset": a, "reason": "missing_owner"} for a in missing_owners)
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if not findings else "error",
        "incidents_checked": checked,
        "glpi_tickets": len(tickets),
        "cmdb_assets": len(assets),
        "findings": findings,
    }
    print(json.dumps(result))
    return bool(findings)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
