"""Fila e timeline contra Postgres real. Pulado sem NINF_TEST_PG_URL.

Ex.: NINF_TEST_PG_URL=postgresql+asyncpg://dev:dev@127.0.0.1:5439/app pytest tests/test_incident_queue.py
"""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routers.incidents import router
from app.core.dependencies import get_current_user
from app.database import Base
from app.models.models import Asset, Incident, IncidentAction
from app.models.users import UserRole

URL = os.environ.get("NINF_TEST_PG_URL")
pytestmark = [
    pytest.mark.skipif(not URL, reason="NINF_TEST_PG_URL não definido"),
    pytest.mark.asyncio,
]

T0 = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def maker():
    engine = create_async_engine(URL)
    tabs = [Asset.__table__, Incident.__table__, IncidentAction.__table__]
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=tabs))
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as c:  # não deixa tipos/tabelas para outros testes
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
    await engine.dispose()


async def _inc(maker, n, *, sev=3, status="open", hours=0, tenant="a", **kw):
    async with maker() as s:
        s.add(
            Incident(
                id=n,
                fingerprint=f"fp{n}",
                title=f"inc{n}",
                severity=sev,
                status=status,
                host_id="h",
                host_name="h",
                trigger_id="t",
                first_seen=T0 + timedelta(hours=hours),
                last_seen=T0 + timedelta(hours=hours),
                tags={"ninf_customer_name": tenant},
                **kw,
            )
        )
        await s.commit()


async def _act(maker, incident_id, action, minutes, **kw):
    async with maker() as s:
        s.add(
            IncidentAction(
                incident_id=incident_id,
                actor_source=kw.pop("source", "user"),
                action=action,
                created_at=T0 + timedelta(minutes=minutes),
                **kw,
            )
        )
        await s.commit()


def _client(maker, role=UserRole.noc, tenant_id=None):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, role=role, tenant_id=tenant_id
    )
    patcher = patch("app.api.routers.incidents.SessionLocal", maker)
    patcher.start()
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    c._patcher = patcher
    return c


@pytest_asyncio.fixture
async def api(maker):
    c = _client(maker)
    yield c
    c._patcher.stop()
    await c.aclose()


def _ids(r):
    return [i["id"] for i in r.json()["incidents"]]


async def test_order_severity_then_status_then_waiting_time(maker, api):
    await _inc(maker, 1, sev=3, hours=0)
    await _inc(maker, 2, sev=5, hours=5)  # mais grave, mais novo: vem primeiro
    await _inc(maker, 3, sev=3, hours=-3)  # mesma severidade, espera maior
    await _inc(maker, 4, sev=5, status="resolved", hours=-9)  # resolvido: depois
    await _inc(maker, 5, sev=5, status="acknowledged", hours=7)
    r = await api.get("/api/incidents")
    assert _ids(r) == ["2", "5", "4", "3", "1"]
    # last_seen desc (ordem antiga) daria outra sequência
    first = r.json()["incidents"][0]
    assert first["age_seconds"] > 0 and first["assigned_user_id"] is None


async def test_pagination_keeps_priority_order(maker, api):
    for n in range(1, 5):
        await _inc(maker, n, sev=n)
    r = await api.get("/api/incidents?limit=2&offset=1")
    assert _ids(r) == ["3", "2"] and r.json()["total"] == 4


async def test_filters_assignee_and_first_seen_range(maker, api):
    await _inc(maker, 1, hours=0, assigned_user_id=9)
    await _inc(maker, 2, hours=10, assigned_user_id=9)
    await _inc(maker, 3, hours=20)
    assert _ids(await api.get("/api/incidents?assignee=9")) == ["1", "2"]
    frm = (T0 + timedelta(hours=5)).isoformat()
    to = "2026-11-02T04:00:00-03:00"  # = 07:00Z: inclui 2 (T0+10h), exclui 3 (T0+20h)
    r = await api.get("/api/incidents", params={"from": frm})
    assert _ids(r) == ["2", "3"] and r.json()["total"] == 2
    r = await api.get("/api/incidents", params={"from": frm, "to": to})
    assert _ids(r) == ["2"]
    assert _ids(await api.get("/api/incidents?status=open&assignee=9")) == ["1", "2"]


@pytest.mark.parametrize("param", ("from", "to"))
@pytest.mark.parametrize("value", ("2026-11-01T10:00:00", "2026-11-01", "lixo"))
async def test_dates_without_timezone_are_422(api, param, value):
    assert (await api.get(f"/api/incidents?{param}={value}")).status_code == 422


async def test_tenant_does_not_leak_in_list_or_timeline(maker):
    await _inc(maker, 1, tenant="a")
    await _inc(maker, 2, tenant="b")
    await _act(maker, 2, "comment", 1, note="segredo de b")
    c = _client(maker, UserRole.viewer, "a")
    try:
        assert _ids(await c.get("/api/incidents")) == ["1"]
        assert (await c.get("/api/incidents/2/timeline")).status_code == 404
        assert (await c.get("/api/incidents/1/timeline")).status_code == 200
    finally:
        c._patcher.stop()
        await c.aclose()


async def test_ticket_state_three_cases(maker, api):
    await _inc(maker, 1, deskmanager_ticket_id="T1")
    await _inc(maker, 2)
    await _inc(maker, 3)
    await _inc(maker, 4)
    await _inc(maker, 5, deskmanager_ticket_id="T5")
    await _act(maker, 1, "ticket_created", 1, source="glpi")
    await _act(maker, 3, "ticket_failed", 1, source="glpi")
    await _act(maker, 4, "ticket_failed", 1, source="glpi")
    await _act(maker, 4, "ticket_retry_exhausted", 2, source="glpi")
    await _act(maker, 5, "ticket_failed", 1, source="glpi")  # já tem ticket
    await _act(maker, 2, "comment", 1, note="x")  # não é ação de ticket
    got = {
        i["id"]: i["ticket_state"]
        for i in (await api.get("/api/incidents")).json()["incidents"]
    }
    assert got == {
        "1": "ticketed",
        "2": "none",
        "3": "pending_sync",
        "4": "pending_sync",
        "5": "ticketed",
    }
    assert (await api.get("/api/incidents/3")).json()["ticket_state"] == "pending_sync"


async def test_ticket_recovered_after_failure_is_not_pending(maker, api):
    await _inc(maker, 1)  # reaberto sem ticket local mas última ação é de sucesso
    await _act(maker, 1, "ticket_failed", 1, source="glpi")
    await _act(maker, 1, "ticket_reused", 2, source="glpi")
    r = await api.get("/api/incidents")
    assert r.json()["incidents"][0]["ticket_state"] == "none"


async def test_timeline_ascending_total_and_pagination(maker, api):
    await _inc(maker, 1)
    for m, a in ((30, "resolve"), (10, "incident_created"), (20, "acknowledge")):
        await _act(
            maker,
            1,
            a,
            m,
            actor_user_id=42 if a != "incident_created" else None,
            source="user" if a != "incident_created" else "zabbix",
            note=a,
        )
    r = await api.get("/api/incidents/1/timeline")
    body = r.json()
    assert [e["kind"] for e in body["entries"]] == [
        "incident_created",
        "acknowledge",
        "resolve",
    ]
    assert body["total"] == 3 and body["limit"] == 200
    e = body["entries"][1]
    assert e["actor"] == {"source": "user", "user_id": 42}
    assert e["source_table"] == "n_infraops_incident_actions"
    assert e["source_id"].isdigit() and e["note"] == "acknowledge"
    assert datetime.fromisoformat(e["at"]).tzinfo is not None
    page = (await api.get("/api/incidents/1/timeline?limit=1&offset=1")).json()
    assert [x["kind"] for x in page["entries"]] == ["acknowledge"]
    assert page["total"] == 3
    assert (await api.get("/api/incidents/1/timeline?limit=501")).status_code == 422
    assert (await api.get("/api/incidents/99/timeline")).status_code == 404
