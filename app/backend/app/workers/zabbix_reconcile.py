"""Reconcilia incidentes `problem` do Hub com os problemas abertos no Zabbix.

O webhook de recuperação pode se perder; sem este passo o incidente fica `problem` para
sempre (painel mostra queda que já voltou e o chamado não fecha sozinho). A recuperação usa
o mesmo caminho do webhook (`_async_process_recovery`).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import String, exists, select
from sqlalchemy.orm import aliased

from app.database import SessionLocal
from app.integrations.zabbix import ZabbixClient
from app.models import Incident, TicketLink
from app.workers import alerts
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Alerta recém-chegado ainda pode não estar na leitura do Zabbix.
MIN_AGE = timedelta(minutes=10)
# ponytail: lote por ciclo; o resto sai nos próximos (15 min). Subir só se o atraso importar.
BATCH = 50
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
    # Vínculo com incidente ainda ativo não fecha: fica fora antes do lote.
    active = aliased(Incident)
    still_active = exists().where(
        active.tags["ninf_dedup_key"].astext == Incident.tags["ninf_dedup_key"].astext,
        active.tags["ninf_entity_id"].astext == Incident.tags["ninf_entity_id"].astext,
        active.tags["ninf_zabbix_status"].astext == "problem",
        active.status.in_(("open", "acknowledged")),
    )
    async with SessionLocal() as session:
        rows = await session.execute(
            select(Incident, TicketLink.entity_id, TicketLink.dedup_key)
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
                ~still_active,
            )
            .order_by(Incident.last_seen)
        )
        # Um incidente por vínculo: vários incidentes do mesmo vínculo não esgotam o lote.
        seen: dict[tuple, Incident] = {}
        for inc, entity_id, dedup in rows.all():
            seen.setdefault((entity_id, dedup), inc)
        return list(seen.values())[:BATCH]


async def _recover(incidents: list[Incident], out: dict[str, int]) -> None:
    for inc in incidents:
        try:
            await alerts._async_process_recovery(
                {
                    "event_id": inc.tags["ninf_zabbix_event_id"],
                    "host_id": inc.host_id,
                    "trigger_id": inc.trigger_id,
                },
                inc.fingerprint,
            )
            out["recovered"] += 1
        except Exception as exc:
            logger.warning("Reconciliação Zabbix falhou: %s", type(exc).__name__)
            out["failed"] += 1


async def reconcile(now: datetime, apply: bool = True) -> dict[str, int]:
    out = {"retried": 0, "stale": 0, "recovered": 0, "failed": 0}
    # Repetir fechamento de chamado não depende do Zabbix: roda antes e sozinho.
    retry = await unclosed_tickets(now)
    out["retried"] = len(retry)
    if apply:
        await _recover(retry, out)

    zabbix = ZabbixClient()
    problems = await zabbix._call(
        "problem.get", {"output": ["eventid"], "recent": False}
    )
    if not isinstance(problems, list):
        return out
    stale = await stale_incidents(now, {str(p["eventid"]) for p in problems})
    if not problems and len(stale) > EMPTY_MAX:
        stale = []
    if stale:
        # Token com permissão por grupo de hosts devolve lista incompleta: só confia
        # em quem tem o host visível. ponytail: host apagado no Zabbix fica de fora.
        hosts = await zabbix._call(
            "host.get",
            {"output": ["hostid"], "hostids": sorted({i.host_id for i in stale})},
        )
        visible = {str(h["hostid"]) for h in hosts or []}
        stale = [i for i in stale if i.host_id in visible][:BATCH]
    out["stale"] = len(stale)
    if apply:
        await _recover(stale, out)
    return out


# Cada recuperação pode falar com o GLPI (timeout de 10 s): o lote de 50 cabe nestes limites.
@celery_app.task(
    name="app.workers.zabbix_reconcile.reconcile_zabbix",
    soft_time_limit=600,
    time_limit=660,
)
def reconcile_zabbix() -> dict[str, int]:
    redis = alerts._get_sync_redis()
    try:
        if not redis.set("ninf:zabbix_reconcile", "1", ex=700, nx=True):
            return {"skipped": 1}
        try:
            return asyncio.run(reconcile(datetime.now(timezone.utc)))
        finally:
            redis.delete("ninf:zabbix_reconcile")
    finally:
        redis.close()
