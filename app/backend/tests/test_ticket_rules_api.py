"""CRUD das regras de chamado (ruído, ação, causa): leitura NOC, escrita só platform_admin."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routers import ticket_rules
from app.core.dependencies import get_current_user
from app.database import Base, get_db
from app.models import TicketRule, UserRole

URL = os.environ.get("NINF_TEST_PG_URL")
SQL004 = (Path(__file__).parents[1] / "sql" / "004_ticket_policy.sql").read_text()
BASE = "/api/ticket-rules"

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def maker():
    if not URL:
        pytest.skip("NINF_TEST_PG_URL não definido")
    engine = create_async_engine(URL)
    async with engine.begin() as c:
        await c.run_sync(
            lambda sc: Base.metadata.drop_all(sc, tables=[TicketRule.__table__])
        )
        await c.run_sync(
            lambda sc: Base.metadata.create_all(sc, tables=[TicketRule.__table__])
        )
        for stmt in SQL004.split(";"):
            if "ticket_rules" in stmt:
                await c.execute(text(stmt))
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as c:
        await c.run_sync(
            lambda sc: Base.metadata.drop_all(sc, tables=[TicketRule.__table__])
        )
    await engine.dispose()


def _api(maker, role):
    app = FastAPI()
    app.include_router(ticket_rules.router)

    async def db():
        async with maker() as s:
            yield s

    user = SimpleNamespace(id=7, role=role, tenant_id=None, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_rule_listed_for_noc(maker):
    async with _api(maker, UserRole.noc) as c:
        r = await c.get(BASE)
    assert r.status_code == 200
    assert {x["kind"] for x in r.json()} == {"noise", "action", "cause"}


async def test_rule_write_needs_platform_admin(maker):
    body = {"kind": "noise", "pattern": "VM3DService"}
    for role in (UserRole.noc, UserRole.admin, UserRole.cliente):
        async with _api(maker, role) as c:
            assert (await c.post(BASE, json=body)).status_code == 403
            assert (
                await c.patch(f"{BASE}/1", json={"enabled": False})
            ).status_code == 403
            assert (await c.delete(f"{BASE}/1")).status_code == 403


async def test_rule_rejects_invalid_regex(maker):
    async with _api(maker, UserRole.platform_admin) as c:
        r = await c.post(BASE, json={"kind": "noise", "pattern": "("})
    assert r.status_code == 422


async def test_rule_rejects_unknown_kind_and_empty_or_long_pattern(maker):
    async with _api(maker, UserRole.platform_admin) as c:
        assert (
            await c.post(BASE, json={"kind": "x", "pattern": "a"})
        ).status_code == 422
        assert (
            await c.post(BASE, json={"kind": "noise", "pattern": " "})
        ).status_code == 422
        assert (
            await c.post(BASE, json={"kind": "noise", "pattern": "a" * 201})
        ).status_code == 422


async def test_rule_create_toggle_delete_and_duplicate_409(maker):
    body = {"kind": "noise", "pattern": "VM3DService", "note": "máquina virtual"}
    async with _api(maker, UserRole.platform_admin) as c:
        r = await c.post(BASE, json=body)
        assert r.status_code == 201
        rid = r.json()["id"]
        assert (await c.post(BASE, json=body)).status_code == 409
        r = await c.patch(f"{BASE}/{rid}", json={"enabled": False})
        assert r.status_code == 200 and r.json()["enabled"] is False
        assert (await c.delete(f"{BASE}/{rid}")).status_code == 204
        assert (await c.delete(f"{BASE}/{rid}")).status_code == 404


async def test_rule_rejects_nested_quantifier(maker):
    async with _api(maker, UserRole.platform_admin) as c:
        for bad in (
            "(a+)+$",
            "(a*)*b",
            "(x{1,5})+",
            "((ab)+)*",
            "(a|aa)+",
        ):
            assert (
                await c.post(BASE, json={"kind": "noise", "pattern": bad})
            ).status_code == 422
        assert (
            await c.post(BASE, json={"kind": "noise", "pattern": "VM3D(Service)?|a+b"})
        ).status_code == 201
