#!/usr/bin/env python3
"""Backfill: marca como recuperados os incidentes `problem` cujo evento o Zabbix já fechou.

Roda dentro do contêiner da API: `docker exec -i ninf-api python - [--apply] [--limit N] < este-arquivo`.
Padrão é dry-run (só lê). Não muda `status` (só o GLPI resolve) nem publica no SSE.
Marca `ninf_zabbix_backfill` na tag e grava ação `zabbix_recovered` com ator `backfill`.
Rollback: tag `ninf_zabbix_status`=problem, remover `ninf_zabbix_recovered_at`/`ninf_zabbix_backfill`
e apagar as ações com actor_source='backfill' (ids pela tag; nunca por faixa).
ponytail: evento já apagado pelo housekeeping do Zabbix fica `problem` e é só contado;
upgrade path: decidir com o Ricardo se vira `unknown`.
"""

import asyncio
import sys
from datetime import datetime, timezone

BATCH = 500


def split_events(events: list[dict]) -> tuple[dict[str, str], list[str]]:
    """({eventid: r_eventid recuperado}, [eventid ainda aberto])."""
    done = {
        e["eventid"]: e["r_eventid"]
        for e in events
        if e.get("r_eventid") not in (None, "", "0")
    }
    return done, [e["eventid"] for e in events if e["eventid"] not in done]


async def main(apply: bool, limit: int | None) -> None:
    from sqlalchemy import select

    from app.database import SessionLocal
    from app.integrations.zabbix import ZabbixClient
    from app.models.models import Incident, IncidentAction

    z = ZabbixClient()
    stamp = datetime.now(timezone.utc).date().isoformat()
    total = recovered = still_open = gone = 0
    last_id = 0
    while not limit or total < limit:
        async with SessionLocal() as session:
            async with session.begin():
                stmt = (
                    select(Incident)
                    .where(
                        Incident.id > last_id,
                        Incident.tags["ninf_zabbix_status"].astext == "problem",
                        Incident.tags.has_key("ninf_zabbix_event_id"),
                    )
                    .order_by(Incident.id)
                    .limit(min(BATCH, limit - total) if limit else BATCH)
                )
                if apply:
                    stmt = stmt.with_for_update()  # espera o worker; nunca pula linha
                rows = (await session.execute(stmt)).scalars().all()
                if not rows:
                    break
                last_id = rows[-1].id
                by_event = {str(r.tags["ninf_zabbix_event_id"]): r for r in rows}
                events = await z._call(
                    "event.get",
                    {"eventids": list(by_event), "output": ["eventid", "r_eventid"]},
                )
                done, opened = split_events(events or [])
                gone += len(by_event) - len(events or [])
                still_open += len(opened)
                clocks = {}
                if done:
                    rec = await z._call(
                        "event.get",
                        {
                            "eventids": list(done.values()),
                            "output": ["eventid", "clock"],
                        },
                    )
                    clocks = {e["eventid"]: int(e["clock"]) for e in rec or []}
                for eid, reid in done.items():
                    inc = by_event[eid]
                    at = (
                        datetime.fromtimestamp(clocks[reid], timezone.utc)
                        if reid in clocks
                        else None
                    )
                    if at is None:
                        gone += 1
                        continue
                    recovered += 1
                    if apply:
                        inc.tags = {
                            **inc.tags,
                            "ninf_zabbix_status": "resolved",
                            "ninf_zabbix_recovered_at": at.isoformat(),
                            "ninf_zabbix_backfill": stamp,
                        }
                        session.add(
                            IncidentAction(
                                incident_id=inc.id,
                                actor_source="backfill",
                                action="zabbix_recovered",
                                previous_status=inc.status,
                                new_status=inc.status,
                                previous_assignee_id=inc.assigned_user_id,
                                new_assignee_id=inc.assigned_user_id,
                                note=f"event={eid} recovery={reid}",
                            )
                        )
                total += len(rows)
    mode = "APPLIED" if apply else "DRY-RUN"
    print(
        f"{mode} examined={total} recovered={recovered} still_open={still_open} not_found={gone}"
    )


if __name__ == "__main__":
    args = sys.argv[1:]
    n = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    asyncio.run(main("--apply" in args, n))
