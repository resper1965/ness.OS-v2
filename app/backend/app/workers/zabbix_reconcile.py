"""Reconcilia incidentes `problem` do Hub com os problemas abertos no Zabbix.

O webhook de recuperação pode se perder; sem este passo o incidente fica `problem` para
sempre (painel mostra queda que já voltou e o chamado não fecha sozinho). A recuperação usa
o mesmo caminho do webhook (`_async_process_recovery`).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import String, select

from app.database import SessionLocal
from app.integrations.zabbix import ZabbixClient
from app.models import Incident, TicketLink
from app.workers import alerts
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Alerta recém-chegado ainda pode não estar na leitura do Zabbix.
MIN_AGE = timedelta(minutes=10)
# ponytail: lote por ciclo; o resto sai nos próximos (15 min). Subir só se o atraso importar.
BATCH = 200
# Lista vazia é legítima (o último problema se recuperou), mas um token sem permissão
# também devolve vazio: com muita coisa a recuperar, não confia.
EMPTY_MAX = 20
# Recuperação já gravada cujo chamado ficou aberto (GLPI fora do ar): tenta de novo por 24 h.
RETRY_WINDOW = timedelta(hours=24)


async def stale_incidents(now: datetime, open_ids: set[str]) -> list[Incident]:
    async with SessionLocal() as session:
        rows = await session.execute(
            select(Incident)
            .where(
                Incident.status.in_(("open", "acknowledged")),
                Incident.tags["ninf_zabbix_status"].astext == "problem",
                Incident.tags["ninf_zabbix_event_id"].astext.regexp_match("^[0-9]+$"),
                Incident.first_seen < now - MIN_AGE,
            )
            .order_by(Incident.first_seen)
        )
        return [
            i for i in rows.scalars() if i.tags["ninf_zabbix_event_id"] not in open_ids
        ]


async def unclosed_tickets(now: datetime) -> list[Incident]:
    async with SessionLocal() as session:
        rows = await session.execute(
            select(Incident)
            .join(
                TicketLink,
                (TicketLink.dedup_key == Incident.tags["ninf_dedup_key"].astext)
                & (
                    TicketLink.entity_id.cast(String)
                    == Incident.tags["ninf_entity_id"].astext
                ),
            )
            .where(
                Incident.tags["ninf_zabbix_status"].astext == "resolved",
                Incident.tags["ninf_zabbix_event_id"].astext.regexp_match("^[0-9]+$"),
                Incident.last_seen > now - RETRY_WINDOW,
                TicketLink.state == "open",
                TicketLink.source_resolved_at.is_(None),
            )
            .order_by(Incident.last_seen)
            .limit(BATCH)
        )
        return list(rows.scalars().unique())


async def reconcile(now: datetime, apply: bool = True) -> dict[str, int]:
    problems = await ZabbixClient()._call(
        "problem.get", {"output": ["eventid"], "recent": False}
    )
    if not isinstance(problems, list):
        return {"skipped": 1}
    stale = await stale_incidents(now, {str(p["eventid"]) for p in problems})
    if not problems and len(stale) > EMPTY_MAX:
        return {"skipped": 1}
    stale += [i for i in await unclosed_tickets(now) if i not in stale]
    out = {
        "zabbix_open": len(problems),
        "stale": len(stale),
        "recovered": 0,
        "failed": 0,
    }
    if not apply:
        return out
    for inc in stale[:BATCH]:
        t = inc.tags
        try:
            await alerts._async_process_recovery(
                {
                    "event_id": t["ninf_zabbix_event_id"],
                    "host_id": inc.host_id,
                    "trigger_id": inc.trigger_id,
                },
                inc.fingerprint,
            )
            out["recovered"] += 1
        except Exception as exc:
            # ponytail: falha do GLPI após marcar recuperado deixa o vínculo aberto; sem retry aqui.
            logger.warning("Reconciliação Zabbix falhou: %s", type(exc).__name__)
            out["failed"] += 1
    return out


@celery_app.task(name="app.workers.zabbix_reconcile.reconcile_zabbix")
def reconcile_zabbix() -> dict[str, int]:
    redis = alerts._get_sync_redis()
    try:
        if not redis.set("ninf:zabbix_reconcile", "1", ex=600, nx=True):
            return {"skipped": 1}
        try:
            return asyncio.run(reconcile(datetime.now(timezone.utc)))
        finally:
            redis.delete("ninf:zabbix_reconcile")
    finally:
        redis.close()
