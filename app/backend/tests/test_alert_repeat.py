"""Repeated Zabbix alert becomes a followup on the open root ticket. Real Postgres.

Ex.: NINF_TEST_PG_URL=postgresql+asyncpg://dev:dev@127.0.0.1:5439/app pytest tests/test_alert_repeat.py
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.integrations.glpi import GLPITransientError
from app.models.models import (
    AIDecision,
    Asset,
    Customer,
    CustomerAlias,
    Incident,
    IncidentAction,
)
from app.workers import alerts, resolution

URL = os.environ.get("NINF_TEST_PG_URL")
pytestmark = [
    pytest.mark.skipif(not URL, reason="NINF_TEST_PG_URL não definido"),
    pytest.mark.asyncio,
]

TABLES = [
    Customer.__table__,
    CustomerAlias.__table__,
    Asset.__table__,
    Incident.__table__,
    IncidentAction.__table__,
    AIDecision.__table__,
]
RESERVATIONS = (
    Path(__file__).parents[1] / "sql" / "003_glpi_ticket_post_reservations.sql"
).read_text()


class Glpi:
    """In-memory GLPI: tickets by title marker, public followups, injectable failures."""

    def __init__(self):
        self.tickets: dict[str, int] = {}
        self.creates = 0
        self.followups: list[tuple[int, str]] = []
        self.fail_create = 0
        self.fail_comment = 0

    async def init_session(self):
        return "s"

    async def kill_session(self):
        return True

    async def change_active_entity(self, entity_id):
        return None

    async def find_ticket_by_name_marker(self, marker, entity_id):
        return self.tickets.get(marker)

    async def create_ticket(self, *, title, **_kw):
        if self.fail_create:
            self.fail_create -= 1
            raise GLPITransientError("GLPI 503")
        self.creates += 1
        ticket_id = 100 + self.creates
        self.tickets[title.split(" ", 1)[0]] = ticket_id
        return {"id": ticket_id}

    async def add_comment(self, ticket_id, content, private=False):
        if private:  # the creation note, not a followup
            return {"id": 1}
        if self.fail_comment:
            self.fail_comment -= 1
            raise GLPITransientError("GLPI 503")
        self.followups.append((ticket_id, content))
        return {"id": 1}


@pytest_asyncio.fixture
async def env(monkeypatch):
    engine = create_async_engine(URL)
    async with engine.begin() as c:
        await c.execute(
            text("DROP TABLE IF EXISTS n_infraops_glpi_ticket_post_reservations")
        )
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=TABLES))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=TABLES))
        await c.execute(text(RESERVATIONS))
    maker = async_sessionmaker(engine, expire_on_commit=False)
    glpi = Glpi()
    gate = AsyncMock(return_value="skipped_customer")  # never reach a real model
    customer = {"name": "Cavan"}
    monkeypatch.setattr(alerts, "SessionLocal", maker)
    monkeypatch.setattr(alerts, "GLPIClient", lambda: glpi)
    monkeypatch.setattr(alerts, "_ai_skip", gate)
    monkeypatch.setattr(alerts.settings, "llm_api_key", "synthetic-key")
    monkeypatch.setattr(alerts.settings, "zabbix_repeat_followup_enabled", True)
    monkeypatch.setattr(alerts, "resolve_alert_customer", AsyncMock(return_value="x"))
    monkeypatch.setattr(
        alerts,
        "canonical_customer",
        AsyncMock(side_effect=lambda _n: (customer["name"], 8)),
    )
    monkeypatch.setattr(alerts, "lookup_glpi_asset", AsyncMock(return_value=None))
    monkeypatch.setattr(alerts, "_get_sync_redis", lambda: MagicMock())
    monkeypatch.setattr(alerts, "LokiClient", lambda: AsyncMock())
    yield maker, glpi, gate, customer
    async with engine.begin() as c:
        await c.execute(
            text("DROP TABLE IF EXISTS n_infraops_glpi_ticket_post_reservations")
        )
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=TABLES))
    await engine.dispose()


def fp(event):
    return str(event).rjust(64, "0")


async def problem(event, trigger="200", host="100"):
    alert = {
        "host_id": host,
        "trigger_id": trigger,
        "host_name": "srv-<1>",
        "trigger_name": "CPU alta",
        "severity": 4,
        "event_id": str(event),
    }
    return await alerts._async_process_alert_v1(alert, fp(event))


async def incident(maker, event):
    async with maker() as s:
        return (
            await s.execute(select(Incident).where(Incident.fingerprint == fp(event)))
        ).scalar_one()


async def actions(maker, incident_id):
    async with maker() as s:
        rows = await s.execute(
            select(IncidentAction.action).where(
                IncidentAction.incident_id == incident_id
            )
        )
        return list(rows.scalars())


async def test_repeat_same_host_trigger_is_followup(env):
    maker, glpi, gate, _ = env
    await problem(1)
    result = await problem(2)

    assert glpi.creates == 1
    assert len(glpi.followups) == 1
    ticket, body = glpi.followups[0]
    assert ticket == 101 and "srv-&lt;1&gt;" in body and "evento 2" in body
    assert result["ticket_id"] == 101
    root, repeat = await incident(maker, 1), await incident(maker, 2)
    assert repeat.repeat_of_id == root.id and repeat.deskmanager_ticket_id is None
    assert repeat.tags["ninf_repeat_ticket_id"] == "101"
    assert repeat.tags["ninf_repeat_followup"] == "done"
    assert "repeat_followup" in await actions(maker, repeat.id)
    assert gate.await_count == 1  # only the root reached the gate
    async with maker() as s:
        row = (
            await s.execute(
                select(AIDecision).where(AIDecision.incident_id == repeat.id)
            )
        ).scalar_one()
    assert (row.outcome, row.model_value) == ("skipped_repeat", None)


async def test_flapping_after_recovery_is_followup(env):
    maker, glpi, _, _ = env
    await problem(1)
    await alerts._async_process_alert_v1(
        {"status": "OK", "host_id": "100", "trigger_id": "200", "event_id": "1"},
        fp(1),
    )
    await problem(2)
    assert (glpi.creates, len(glpi.followups)) == (1, 1)


async def test_resolved_root_opens_new_ticket(env):
    maker, glpi, _, _ = env
    await problem(1)
    async with maker() as s, s.begin():
        (await s.get(Incident, (await incident(maker, 1)).id)).status = "resolved"
    await problem(2)
    assert (glpi.creates, glpi.followups) == (2, [])
    assert (await incident(maker, 2)).repeat_of_id is None


async def test_closed_root_opens_new_ticket(env):
    maker, glpi, _, _ = env
    await problem(1)
    async with maker() as s, s.begin():
        (await s.get(Incident, (await incident(maker, 1)).id)).status = "closed"
    await problem(2)
    assert (glpi.creates, glpi.followups) == (2, [])
    assert (await incident(maker, 2)).repeat_of_id is None


async def test_followup_state_query_failure_keeps_own_ticket(env, monkeypatch):
    maker, glpi, _, _ = env
    await problem(1)
    real = alerts.find_open_root

    async def found_then_fails(session, **kw):
        root = await real(session, **kw)
        assert root is not None
        session.execute = AsyncMock(side_effect=RuntimeError("db"))
        await session.execute("followup state")  # any later query in the lookup
        return root

    monkeypatch.setattr(alerts, "find_open_root", found_then_fails)
    await problem(2)
    assert (glpi.creates, glpi.followups) == (2, [])
    assert (await incident(maker, 2)).repeat_of_id is None


async def test_redelivered_repeat_after_root_resolved_stays_linked(env):
    maker, glpi, gate, _ = env
    await problem(1)
    await problem(2)
    async with maker() as s, s.begin():
        (await s.get(Incident, (await incident(maker, 1)).id)).status = "resolved"
    result = await problem(2)
    assert (glpi.creates, len(glpi.followups)) == (1, 1)
    assert result["ticket_id"] == 101
    repeat = await incident(maker, 2)
    assert repeat.repeat_of_id == (await incident(maker, 1)).id
    assert repeat.deskmanager_ticket_id is None and repeat.status == "open"
    assert gate.await_count == 1


async def test_root_without_ticket_is_not_reused(env):
    maker, glpi, _, _ = env
    glpi.fail_create = 1
    with pytest.raises(GLPITransientError):
        await problem(1)
    await problem(2)
    assert (glpi.creates, glpi.followups) == (1, [])
    assert (await incident(maker, 2)).deskmanager_ticket_id == "101"


async def test_repeat_never_crosses_customers(env):
    _, glpi, _, customer = env
    await problem(1)
    customer["name"] = "Unimed"
    await problem(2)
    assert (glpi.creates, glpi.followups) == (2, [])


async def test_other_trigger_same_host_opens_ticket(env):
    _, glpi, _, _ = env
    await problem(1)
    await problem(2, trigger="201")
    assert (glpi.creates, glpi.followups) == (2, [])


async def test_repeat_retry_single_followup(env):
    maker, glpi, _, _ = env
    await problem(1)
    glpi.fail_comment = 1
    with pytest.raises(GLPITransientError):
        await problem(2)
    repeat = await incident(maker, 2)
    assert repeat.repeat_of_id is not None and "ninf_repeat_followup" not in (
        repeat.tags
    )
    await problem(2)
    await problem(2)
    assert (glpi.creates, len(glpi.followups)) == (1, 1)
    assert (await actions(maker, repeat.id)).count("repeat_followup") == 1


async def test_root_lookup_failure_falls_back_to_ticket(env, monkeypatch):
    _, glpi, _, _ = env
    await problem(1)
    monkeypatch.setattr(
        alerts, "find_open_root", AsyncMock(side_effect=RuntimeError("db"))
    )
    await problem(2)
    assert (glpi.creates, glpi.followups) == (2, [])


async def test_resolve_root_resolves_repeats(env, monkeypatch):
    maker, _, _, _ = env
    await problem(1)
    await problem(2)
    monkeypatch.setattr(resolution, "SessionLocal", maker)
    monkeypatch.setattr(resolution, "resolve_glpi_entity_id", AsyncMock(return_value=8))
    g = MagicMock(kill_session=AsyncMock())
    g.ticket_resolution = AsyncMock(
        return_value={"resolved": True, "solution": "", "solution_id": "9"}
    )
    monkeypatch.setattr(resolution, "GLPIClient", lambda: g)
    z = MagicMock(acknowledge_resolution_once=AsyncMock(return_value="success"))
    monkeypatch.setattr(resolution, "ZabbixClient", lambda: z)

    await resolution.resolve_ticket("101", MagicMock())

    root, repeat = await incident(maker, 1), await incident(maker, 2)
    assert (root.status, repeat.status) == ("resolved", "resolved")
    assert "root_resolved" in await actions(maker, repeat.id)
    z.acknowledge_resolution_once.assert_awaited_once()  # ack stays on the root


async def test_flag_off_keeps_ticket_per_event(env, monkeypatch):
    maker, glpi, gate, _ = env
    monkeypatch.setattr(alerts.settings, "zabbix_repeat_followup_enabled", False)
    await problem(1)
    await problem(2)
    assert (glpi.creates, glpi.followups) == (2, [])
    assert gate.await_count == 2
    assert (await incident(maker, 2)).repeat_of_id is None
