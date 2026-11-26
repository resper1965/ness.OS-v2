"""Regra de chamados ponta a ponta contra Postgres real, GLPI mockado. Pulado sem NINF_TEST_PG_URL.

Ingestão (pendente/comentário), decisor (carência, causa->sintoma, dedup, reabertura)
e recuperação (fecha o chamado intocado, libera sintomas).
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.integrations.glpi import GLPITransientError
from app.ml.analyzer import AIAnalysisResult
from app.models import (
    Asset,
    Incident,
    IncidentAction,
    PlatformParam,
    TicketLink,
    TicketRule,
)
from app.services.ticket_policy import dedup_key
from app.workers import alerts, ticket_decider

URL = os.environ.get("NINF_TEST_PG_URL")
SQL = Path(__file__).parents[1] / "sql"
TABLES = [Asset, Incident, IncidentAction, PlatformParam, TicketRule, TicketLink]
TABLES = [t.__table__ for t in TABLES]
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
SITE = "[ Unimed ] [ Itu ]"
ANALYSIS = AIAnalysisResult(
    executive_action_plan="x",
    technical_action_plan="x",
    urgency="MEDIUM",
    isolation_required=False,
    probable_cause="x",
    recommended_playbook="x",
)


async def _run_sql(conn, name):
    for stmt in (SQL / name).read_text().split(";"):
        if stmt.strip():
            await conn.execute(text(stmt))


@pytest_asyncio.fixture
async def maker(monkeypatch):
    if not URL:
        pytest.skip("NINF_TEST_PG_URL não definido")
    engine = create_async_engine(URL)
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=TABLES))
        await c.execute(text("DROP TABLE IF EXISTS n_infraops_glpi_ticket_post_reservations"))  # fmt: skip
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=TABLES))
        await c.execute(
            text((SQL / "003_glpi_ticket_post_reservations.sql").read_text())
        )
        await _run_sql(c, "004_ticket_policy.sql")
    m = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(alerts, "SessionLocal", m)
    monkeypatch.setattr(ticket_decider, "SessionLocal", m)
    monkeypatch.setattr(
        ticket_decider, "analyze_incident", AsyncMock(return_value=ANALYSIS)
    )
    monkeypatch.setattr(alerts, "_get_sync_redis", lambda: MagicMock())
    monkeypatch.setattr(alerts, "LokiClient", lambda: AsyncMock())
    yield m
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=TABLES))
        await c.execute(text("DROP TABLE n_infraops_glpi_ticket_post_reservations"))
    await engine.dispose()


@pytest.fixture
def glpi(monkeypatch):
    g = AsyncMock()
    g.session_token = "s"
    g.create_ticket.side_effect = lambda **_: {"id": 500 + g.create_ticket.call_count}
    g.find_ticket_by_name_marker.return_value = None
    g.has_technician.return_value = False
    monkeypatch.setattr(alerts, "GLPIClient", lambda: g)
    monkeypatch.setattr(ticket_decider, "GLPIClient", lambda: g)
    return g


async def _inc(
    maker, n, title, *, minutes=16, entity=12, site=SITE, sev=3, host=None, **tags
):
    async with maker() as s:
        s.add(
            Incident(
                id=n,
                fingerprint=f"fp{n}",
                title=title,
                severity=sev,
                status="open",
                host_id=f"h{n}",
                host_name=host or f"host{n}",
                trigger_id=f"t{n}",
                deskmanager_ticket_id=tags.pop("ticket", None),
                first_seen=NOW - timedelta(minutes=minutes),
                last_seen=NOW,
                tags={
                    "ninf_customer_name": "Unimed",
                    "ninf_entity_id": entity,
                    "ninf_dedup_key": dedup_key(entity, f"h{n}", f"t{n}"),
                    "ninf_zabbix_event_id": str(n),
                    "ninf_zabbix_status": "problem",
                    "ninf_ticket_state": "pending",
                    **({"ninf_site": site} if site else {}),
                    **tags,
                },
            )
        )
        await s.commit()


async def _state(maker, n):
    async with maker() as s:
        return (await s.get(Incident, n)).tags.get("ninf_ticket_state")


async def _link(maker, n, entity=12, **kw):
    async with maker() as s:
        row = TicketLink(
            entity_id=entity, dedup_key=dedup_key(entity, f"h{n}", f"t{n}"), **kw
        )
        s.add(row)
        await s.commit()


TUNNEL = "FortiGate: VPN 17 Boticario: Tunnel down"
DISK = "Linux: FS [/]: Space is critically low"
UPDATER = 'Windows: "X" (GoogleUpdaterService157) is not running'


# ---------- ingestão (Task 4) ----------


def _alert(event="900", host="h1", trigger="t1"):
    return {
        "event_id": event,
        "host_id": host,
        "host_name": "UI-AD-02",
        "trigger_id": trigger,
        "trigger_name": DISK,
        "severity": 3,
    }


@pytest.fixture
def customer(monkeypatch):
    def use(entity):
        monkeypatch.setattr(
            alerts, "resolve_alert_customer", AsyncMock(return_value=("Unimed", SITE))
        )
        monkeypatch.setattr(
            alerts, "canonical_customer", AsyncMock(return_value=("Unimed", entity))
        )

    return use


@pytest.mark.asyncio
async def test_problem_event_is_pending_without_glpi(maker, glpi, customer):
    customer(12)
    r = await alerts._async_process_alert_v1(_alert(), "e1")
    async with maker() as s:
        tags = (await s.get(Incident, r["id"])).tags
    assert tags["ninf_ticket_state"] == "pending" and tags["ninf_site"] == SITE
    assert not glpi.method_calls


@pytest.mark.asyncio
async def test_recurrence_with_open_link_comments_once(maker, glpi, customer):
    customer(12)
    await _link(maker, 1, ticket_id=77)
    r = await alerts._async_process_alert_v1(_alert(event="901"), "e2")
    await alerts._async_process_alert_v1(_alert(event="901"), "e2")  # replay
    glpi.add_comment.assert_awaited_once()
    assert glpi.add_comment.await_args.kwargs["ticket_id"] == 77
    glpi.create_ticket.assert_not_awaited()
    async with maker() as s:
        inc = await s.get(Incident, r["id"])
        link = (await s.execute(select(TicketLink))).scalar_one()
    assert inc.tags["ninf_ticket_state"] == "attached"
    assert inc.deskmanager_ticket_id == "77" and link.occurrences == 2


@pytest.mark.asyncio
async def test_recurrence_other_customer_not_attached(maker, glpi, customer):
    customer(13)
    await _link(maker, 1, entity=12, ticket_id=77)
    r = await alerts._async_process_alert_v1(_alert(), "e3")
    assert await _state(maker, r["id"]) == "pending"
    glpi.add_comment.assert_not_awaited()


# ---------- decisor (Task 5) ----------


@pytest.mark.asyncio
async def test_not_due_before_grace(maker, glpi):
    await _inc(maker, 1, TUNNEL, minutes=14)
    assert (await ticket_decider.decide(NOW))["waiting"] == 1
    assert await _state(maker, 1) == "pending"
    glpi.create_ticket.assert_not_awaited()


@pytest.mark.asyncio
async def test_action_after_grace_opens_one_ticket(maker, glpi):
    await _inc(maker, 1, DISK, site=None)
    await ticket_decider.decide(NOW)
    await ticket_decider.decide(NOW)
    glpi.create_ticket.assert_awaited_once()
    assert await _state(maker, 1) == "opened"
    async with maker() as s:
        link = (await s.execute(select(TicketLink))).scalar_one()
    assert link.state == "open" and link.ticket_id == 501


@pytest.mark.asyncio
async def test_noise_after_grace_is_panel(maker, glpi):
    await _inc(maker, 1, UPDATER, minutes=60)
    await ticket_decider.decide(NOW)
    assert await _state(maker, 1) == "panel"
    glpi.create_ticket.assert_not_awaited()
    glpi.add_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovered_before_grace_never_tickets(maker, glpi):
    await _inc(maker, 1, DISK, ninf_zabbix_status="resolved")
    await ticket_decider.decide(NOW)
    glpi.create_ticket.assert_not_awaited()


@pytest.mark.asyncio
async def test_symptom_suppressed_by_active_cause(maker, glpi):
    await _inc(maker, 1, TUNNEL, minutes=16)
    for n, m in ((2, 17), (3, 14), (4, 11)):  # de 1 min antes a 5 min depois
        await _inc(maker, n, DISK, minutes=m)
    await ticket_decider.decide(NOW)
    glpi.create_ticket.assert_awaited_once()
    assert [await _state(maker, n) for n in (2, 3, 4)] == ["symptom"] * 3

    def symptom_comments():
        return [
            c.kwargs["content"]
            for c in glpi.add_comment.await_args_list
            if "afetados" in c.kwargs["content"]
        ]

    assert len(symptom_comments()) == 1
    assert all(f"host{n}" in symptom_comments()[0] for n in (2, 3, 4))
    await ticket_decider.decide(NOW)
    assert len(symptom_comments()) == 1  # sintomas já citados


@pytest.mark.asyncio
async def test_symptom_waits_for_cause_decision(maker, glpi):
    await _inc(maker, 1, TUNNEL, minutes=10)
    await _inc(maker, 2, DISK, minutes=11)
    await ticket_decider.decide(NOW)
    assert await _state(maker, 2) == "symptom"
    glpi.create_ticket.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_site_never_symptom(maker, glpi):
    await _inc(maker, 1, TUNNEL, minutes=10)
    await _inc(maker, 2, DISK, site=None)
    await ticket_decider.decide(NOW)
    assert await _state(maker, 2) == "opened"


@pytest.mark.asyncio
async def test_cause_other_customer_same_site_name(maker, glpi):
    await _inc(maker, 1, TUNNEL, minutes=10, entity=12)
    await _inc(maker, 2, DISK, entity=13)
    await ticket_decider.decide(NOW)
    assert await _state(maker, 2) == "opened"


@pytest.mark.asyncio
async def test_reopen_within_24h(maker, glpi):
    await _link(
        maker, 1, ticket_id=77, state="auto_closed", closed_at=NOW - timedelta(hours=3)
    )
    await _inc(maker, 1, DISK, site=None)
    await ticket_decider.decide(NOW)
    glpi.reopen_ticket.assert_awaited_once()
    glpi.create_ticket.assert_not_awaited()
    async with maker() as s:
        assert (await s.execute(select(TicketLink.state))).scalar_one() == "open"
        assert (await s.get(Incident, 1)).deskmanager_ticket_id == "77"


@pytest.mark.asyncio
async def test_new_ticket_after_tech_close(maker, glpi):
    await _link(maker, 1, ticket_id=77, state="closed", closed_at=NOW)
    await _inc(maker, 1, DISK, site=None)
    await ticket_decider.decide(NOW)
    glpi.reopen_ticket.assert_not_awaited()
    assert "#77" in glpi.create_ticket.await_args.kwargs["content"]


@pytest.mark.asyncio
async def test_glpi_down_keeps_pending_no_duplicate(maker, glpi):
    await _inc(maker, 1, DISK, site=None)

    def lost(**_):  # GLPI cria, mas a resposta se perde
        glpi.find_ticket_by_name_marker.return_value = 501
        raise GLPITransientError("lost")

    glpi.create_ticket.side_effect = lost
    assert (await ticket_decider.decide(NOW))["failed"] == 1
    assert await _state(maker, 1) == "pending"
    await ticket_decider.decide(NOW)
    glpi.create_ticket.assert_awaited_once()
    async with maker() as s:
        assert (await s.get(Incident, 1)).deskmanager_ticket_id == "501"


# ---------- recuperação (Task 6) ----------


async def _recover(n):
    return await alerts._async_process_recovery(
        {"event_id": str(n), "host_id": f"h{n}", "trigger_id": f"t{n}"}, f"fp{n}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("technician", [False, True])
async def test_recovery_closes_only_untouched_ticket(maker, glpi, technician):
    glpi.has_technician.return_value = technician
    await _inc(maker, 1, DISK, site=None)
    await ticket_decider.decide(NOW)
    await _recover(1)
    await _recover(1)  # replay
    async with maker() as s:
        link = (await s.execute(select(TicketLink))).scalar_one()
        assert (await s.get(Incident, 1)).status == "resolved"
    if technician:
        glpi.solve_ticket.assert_not_awaited()
        assert link.state == "open" and link.source_resolved_at
    else:
        glpi.solve_ticket.assert_awaited_once()
        assert link.state == "auto_closed" and link.closed_at


@pytest.mark.asyncio
async def test_cause_recovery_releases_active_symptoms(maker, glpi):
    await _inc(maker, 1, TUNNEL, minutes=10)
    await _inc(maker, 2, DISK, minutes=10)
    await _inc(maker, 3, DISK, minutes=10)
    await ticket_decider.decide(NOW)
    await _recover(3)
    await _recover(1)
    async with maker() as s:
        two, three = await s.get(Incident, 2), await s.get(Incident, 3)
    assert two.tags["ninf_ticket_state"] == "pending"
    assert two.tags["ninf_grace_from"]
    assert three.tags["ninf_ticket_state"] == "symptom"
    glpi.create_ticket.assert_not_awaited()  # causa nunca venceu a carência


# ---------- revisão do PR (#271) ----------


@pytest.mark.asyncio
async def test_high_severity_is_never_symptom(maker, glpi):
    await _inc(maker, 1, TUNNEL, minutes=16)
    await _inc(maker, 2, DISK, minutes=16, sev=4)
    await ticket_decider.decide(NOW)
    assert await _state(maker, 2) == "opened"
    assert glpi.create_ticket.await_count == 2


@pytest.mark.asyncio
async def test_recovered_during_cycle_does_not_open(maker, glpi):
    await _inc(maker, 1, DISK, site=None)
    async with maker() as s:
        stale = await s.get(Incident, 1)
    await _recover(1)  # chega depois da foto do ciclo
    assert await ticket_decider._open(glpi, stale, NOW, 24) == "skipped"
    glpi.create_ticket.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_during_creation_closes_ticket(maker, glpi):
    await _inc(maker, 1, DISK, site=None)

    async with maker() as s:
        inc = await s.get(Incident, 1)
    orig = ticket_decider.analyze_incident

    async def recover_then_analyze(**kw):
        await _recover(1)
        return await orig(**kw)

    ticket_decider.analyze_incident = recover_then_analyze
    try:
        # a foto ainda está pendente; a recuperação cai no meio da criação
        await ticket_decider._open(glpi, inc, NOW, 24)
    finally:
        ticket_decider.analyze_incident = orig
    async with maker() as s:
        link = (await s.execute(select(TicketLink))).scalar_one()
    assert link.state != "open" or link.source_resolved_at is not None


@pytest.mark.asyncio
async def test_tech_resolution_resolves_all_occurrences(maker, glpi, monkeypatch):
    from app.models import AIDecision
    from app.workers import resolution

    async with maker() as s:
        conn = await s.connection()
        await conn.run_sync(
            lambda sc: Base.metadata.create_all(sc, tables=[AIDecision.__table__])
        )
        await s.commit()

    await _inc(maker, 1, DISK, site=None)
    await ticket_decider.decide(NOW)
    async with maker() as s:
        await s.execute(
            text(
                "UPDATE n_infraops_incidents SET deskmanager_ticket_id='501' WHERE id=1"
            )
        )
        await s.commit()
    await _inc(maker, 2, DISK, site=None)
    async with maker() as s:
        inc2 = await s.get(Incident, 2)
        inc2.deskmanager_ticket_id = "501"
        inc2.tags = {**inc2.tags, "ninf_ticket_state": "attached"}
        await s.commit()
    monkeypatch.setattr(resolution, "SessionLocal", maker)
    monkeypatch.setattr(
        resolution, "resolve_glpi_entity_id", AsyncMock(return_value=12)
    )
    g = MagicMock()
    g.ticket_resolution = AsyncMock(
        return_value={"resolved": True, "solution": "", "solution_id": "9"}
    )
    g.kill_session = AsyncMock()
    monkeypatch.setattr(resolution, "GLPIClient", lambda: g)
    z = MagicMock()
    z.acknowledge_resolution_once = AsyncMock(return_value="success")
    monkeypatch.setattr(resolution, "ZabbixClient", lambda: z)
    await resolution.resolve_ticket("501", MagicMock())
    async with maker() as s:
        assert {(await s.get(Incident, n)).status for n in (1, 2)} == {"resolved"}
        link = (await s.execute(select(TicketLink))).scalar_one()
    assert link.state == "closed"


@pytest.mark.asyncio
async def test_ticket_body_has_summary_and_link(maker, glpi):
    await _inc(maker, 1, DISK, site=None)
    await ticket_decider.decide(NOW)
    body = glpi.create_ticket.call_args.kwargs["content"]
    assert "ver no ness.OS" in body and "/?view=incidents&amp;id=1" in body


async def _opened(maker, n, minutes_ago, branch, host="srv1"):
    await _inc(
        maker,
        n,
        DISK,
        site=None,
        host=host,
        ticket=str(900 + n),
        ninf_ticket_state="opened",
        ninf_ticket_opened_at=(NOW - timedelta(minutes=minutes_ago)).isoformat(),
        ninf_branch=branch,
    )


@pytest.mark.asyncio
async def test_cross_branch_linked_within_window(maker, glpi):
    await _opened(maker, 1, 10, "noc")
    await _inc(maker, 2, DISK, site=None, host="srv1", ninf_branch="soc")
    await ticket_decider.decide(NOW)
    glpi.link_tickets.assert_awaited_once_with(501, 901)
    public = [c for c in glpi.add_comment.await_args_list if not c.kwargs["private"]]
    assert {c.kwargs["ticket_id"] for c in public} == {501, 901}


@pytest.mark.asyncio
async def test_cross_branch_not_linked_outside_window(maker, glpi):
    await _opened(maker, 1, 45, "noc")
    await _inc(maker, 2, DISK, site=None, host="srv1", ninf_branch="soc")
    await ticket_decider.decide(NOW)
    glpi.link_tickets.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_branch_never_cross_linked(maker, glpi):
    await _opened(maker, 1, 10, "noc")
    await _inc(maker, 2, DISK, site=None, host="srv1", ninf_branch="noc")
    await ticket_decider.decide(NOW)
    glpi.link_tickets.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_cross_link_is_retried_once(maker, glpi):
    await _opened(maker, 1, 10, "noc")
    await _inc(maker, 2, DISK, site=None, host="srv1", ninf_branch="soc")
    glpi.link_tickets.side_effect = [RuntimeError("x"), None]
    await ticket_decider.decide(NOW)  # falha ao abrir e repete no fim do mesmo ciclo
    assert glpi.link_tickets.await_count == 2
    await ticket_decider.decide(NOW)  # a marca foi consumida: não repete de novo
    assert glpi.link_tickets.await_count == 2


@pytest.mark.asyncio
async def test_resolved_other_branch_ticket_not_linked(maker, glpi):
    await _opened(maker, 1, 10, "noc")
    async with maker() as s:
        (await s.get(Incident, 1)).status = "resolved"
        await s.commit()
    await _inc(maker, 2, DISK, site=None, host="srv1", ninf_branch="soc")
    await ticket_decider.decide(NOW)
    glpi.link_tickets.assert_not_awaited()


@pytest.mark.asyncio
async def test_soc_ticket_skips_zabbix_asset_lookup(maker, glpi, monkeypatch):
    lookup = AsyncMock(return_value={"itemtype": "Computer", "id": 1})
    monkeypatch.setattr(alerts, "lookup_glpi_asset", lookup)
    await _inc(maker, 1, DISK, site=None, ninf_branch="soc")
    await ticket_decider.decide(NOW)
    lookup.assert_not_awaited()
    assert "linked_item" not in glpi.create_ticket.call_args.kwargs


@pytest.mark.asyncio
async def test_zabbix_reconcile_recovers_only_what_zabbix_no_longer_has(
    maker, glpi, monkeypatch
):
    from app.workers import zabbix_reconcile

    monkeypatch.setattr(zabbix_reconcile, "SessionLocal", maker)
    await _inc(maker, 1, TUNNEL, minutes=60)  # sumiu do Zabbix: recupera
    await _inc(maker, 2, TUNNEL, minutes=60)  # ainda aberto: fica
    await _inc(maker, 3, TUNNEL, minutes=5)  # recente demais: fica
    zabbix = AsyncMock()

    async def call(method, params):
        if method == "host.get":
            return [{"hostid": h} for h in params["hostids"] if h != "h7"]
        return [{"eventid": "2"}]

    zabbix._call.side_effect = call
    monkeypatch.setattr(zabbix_reconcile, "ZabbixClient", lambda: zabbix)
    monkeypatch.setattr(zabbix_reconcile, "MIN_AGE", timedelta(minutes=10))
    await _inc(maker, 7, TUNNEL, minutes=60)  # host invisível ao token: fica

    out = await zabbix_reconcile.reconcile(NOW + timedelta(minutes=1))
    assert out["recovered"] == 1 and out["failed"] == 0
    async with maker() as s:
        assert (await s.get(Incident, 1)).tags["ninf_zabbix_status"] == "resolved"
        assert (await s.get(Incident, 2)).tags["ninf_zabbix_status"] == "problem"
        assert (await s.get(Incident, 3)).tags["ninf_zabbix_status"] == "problem"
        assert (await s.get(Incident, 7)).tags["ninf_zabbix_status"] == "problem"

    # Lista vazia vale quando há poucos a recuperar; com muitos, é suspeita (token sem permissão).
    async def vazio(method, params):
        if method == "host.get":
            return [{"hostid": h} for h in params["hostids"] if h != "h7"]
        return []

    zabbix._call.side_effect = vazio
    out = await zabbix_reconcile.reconcile(NOW + timedelta(minutes=1))
    assert out["recovered"] == 1  # o incidente 2
    monkeypatch.setattr(zabbix_reconcile, "EMPTY_MAX", 0)
    await _inc(maker, 4, TUNNEL, minutes=60)
    out = await zabbix_reconcile.reconcile(NOW + timedelta(minutes=1))
    assert out["recovered"] == 0 and out["stale"] == 0
    async with maker() as s:
        assert (await s.get(Incident, 4)).tags["ninf_zabbix_status"] == "problem"


@pytest.mark.asyncio
async def test_zabbix_reconcile_retries_ticket_closure_after_glpi_failure(
    maker, glpi, monkeypatch
):
    from app.workers import zabbix_reconcile

    monkeypatch.setattr(zabbix_reconcile, "SessionLocal", maker)
    await _inc(maker, 1, DISK, site=None, minutes=60)
    await ticket_decider.decide(NOW)
    zabbix = AsyncMock()

    async def call(method, params):
        if method == "host.get":
            return [{"hostid": h} for h in params["hostids"]]
        return [{"eventid": "999"}]

    zabbix._call.side_effect = call
    monkeypatch.setattr(zabbix_reconcile, "ZabbixClient", lambda: zabbix)

    glpi.solve_ticket.side_effect = GLPITransientError("fora do ar")
    out = await zabbix_reconcile.reconcile(NOW + timedelta(minutes=1))
    assert out["failed"] == 1
    async with maker() as s:
        assert (await s.get(Incident, 1)).tags["ninf_zabbix_status"] == "resolved"
        assert (await s.execute(select(TicketLink))).scalar_one().state == "open"

    # Outro incidente do mesmo vínculo não consome um segundo lugar no lote.
    await _inc(maker, 8, DISK, site=None, minutes=60, ninf_zabbix_status="resolved")
    async with maker() as s:
        dup = await s.get(Incident, 8)
        dup.tags = {
            **dup.tags,
            "ninf_dedup_key": (await s.get(Incident, 1)).tags["ninf_dedup_key"],
        }
        await s.commit()
    assert len(await zabbix_reconcile.unclosed_tickets(NOW + timedelta(minutes=1))) == 1

    glpi.solve_ticket.side_effect = None
    # Zabbix fora do ar: o reenvio do fechamento ainda acontece.
    zabbix._call.side_effect = RuntimeError("Zabbix API indisponível")
    with pytest.raises(RuntimeError):
        await zabbix_reconcile.reconcile(NOW + timedelta(minutes=2))
    async with maker() as s:
        assert (await s.execute(select(TicketLink))).scalar_one().state == "auto_closed"
