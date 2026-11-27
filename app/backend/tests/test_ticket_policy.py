"""Regras de chamado: esquema/seed (Postgres real) e política pura sobre o seed."""

import os
import re
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Asset, Incident, PlatformParam, TicketLink, TicketRule
from app.services.ticket_policy import (
    classify,
    dedup_key,
    is_cause,
    load_rules,
    site_from_hostgroups,
)

URL = os.environ.get("NINF_TEST_PG_URL")
SQL004 = (Path(__file__).parents[1] / "sql" / "004_ticket_policy.sql").read_text()
TABLES = [Asset.__table__, Incident.__table__, PlatformParam.__table__]
TABLES += [TicketRule.__table__, TicketLink.__table__]


async def apply_004(conn):
    for stmt in SQL004.split(";"):
        if stmt.strip():
            await conn.execute(text(stmt))


@pytest_asyncio.fixture
async def maker():
    if not URL:
        pytest.skip("NINF_TEST_PG_URL não definido")
    engine = create_async_engine(URL)
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=TABLES))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=TABLES))
        await apply_004(c)
        await apply_004(c)  # idempotente
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=TABLES))
    await engine.dispose()


@pytest.mark.asyncio
async def test_ticket_policy_tables_exist_and_seeded(maker):
    async with maker() as s:
        kinds = dict(
            (await s.execute(text("select kind, count(*) from n_infraops_ticket_rules group by 1"))).all()  # fmt: skip
        )
        assert kinds["noise"] > 0 and kinds["action"] > 0 and kinds["cause"] > 0
        params = dict(
            (await s.execute(text("select key, value_int from n_infraops_platform_params"))).all()  # fmt: skip
        )
        assert params["ticket_grace_minutes"] == 15
        assert params["ticket_reopen_hours"] == 24
        assert params["ticket_symptom_lead_minutes"] == 2
        s.add(TicketLink(entity_id=1, dedup_key="k", ticket_id=9))
        await s.commit()
        s.add(TicketLink(entity_id=1, dedup_key="x", ticket_id=9, state="x"))
        with pytest.raises(IntegrityError):
            await s.commit()


@pytest.mark.asyncio
async def test_classify_and_cause_with_seed(maker):
    async with maker() as s:
        r = await load_rules(s)
    gu = (
        'Windows: "X" (GoogleUpdaterService157) is not running (startup type automatic)'
    )
    assert classify(gu, 3, r) == "panel"
    assert classify("FortiGate: VPN 17 Boticario: Tunnel down", 3, r) == "action"
    assert classify("FortiGate: Unavailable by ICMP ping", 4, r) == "action"
    assert classify("Windows: The Memory Pages/sec is too high", 4, r) == "action"
    assert classify("Windows: The Memory Pages/sec is too high", 3, r) == "panel"
    assert classify("Linux: FS [/]: Space is critically low", 3, r) == "action"
    assert classify('Windows: "X" (MSSQLSERVER) is not running', 3, r) == "action"
    dead = "FortiGate: SD-WAN [x]:[wan1]: Health check state is dead"
    assert is_cause(dead, r) is True
    assert is_cause("Windows: High memory utilization", r) is False


@pytest.mark.asyncio
async def test_invalid_pattern_is_skipped(maker):
    async with maker() as s:
        s.add(TicketRule(kind="action", pattern="("))
        await s.commit()
        r = await load_rules(s)
    assert all(p.pattern != "(" for p in r.action)


def test_site_and_dedup_key():
    groups = ["[ Unimed ]", "[ Unimed ] [ Itu ] [ Servidor V ]"]
    assert site_from_hostgroups(groups) == "[ Unimed ] [ Itu ]"
    assert site_from_hostgroups(["[Unimed]   [Itu]"]) == "[Unimed] [Itu]"
    assert site_from_hostgroups(["Templates", "[ Unimed ]"]) is None
    assert dedup_key(12, "1", "2") != dedup_key(13, "1", "2")
    assert re.fullmatch(r"[0-9a-f]{64}", dedup_key(12, "1", "2"))


def test_hit_never_stalls_on_a_pathological_rule():
    import time

    import regex

    from app.services.ticket_policy import _hit

    bad = regex.compile(r"(a|a)*$", regex.I)
    title = "a" * 200 + "b"
    start = time.monotonic()
    assert _hit([bad], title) is False  # ruído: estouro não suprime
    assert _hit([bad], title, fail_open=True) is True  # ação: estouro abre chamado
    assert time.monotonic() - start < 1.0
