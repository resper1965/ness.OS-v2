"""Cadastro de clientes e apelidos contra Postgres real (pulado sem NINF_TEST_PG_URL)."""

from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from app.api.routers.customers import router
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.users import UserRole
from app.services.customers import resolve_customer, resolve_glpi_entity_id

pytestmark = pytest.mark.asyncio

LEGACY = {
    "alupar": 1, "alupar investimento s.a.": 1, "tbe": 2, "target": 3,
    "target trading": 3, "ltb": 4, "leite tosto": 4,
    "leite tosto e barros adv ass": 4, "alupar pe": 5, "alupar-pe": 5,
    "alupar co": 6, "alupar-co": 6, "bichara": 7, "cavan": 8,
    "nova energia": 9, "novaenergia": 9, "numen": 10, "numen it": 10,
    "tne": 11, "unimed": 12, "ness": 0, "ness processos e tecnologia ltda.": 0,
}  # fmt: skip


@pytest.fixture
def api(customers_maker):
    def make(role):
        app = FastAPI()
        app.include_router(router)

        async def db():
            async with customers_maker() as s:
                yield s

        app.dependency_overrides[get_db] = db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=7, role=role
        )
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        )

    return make


async def test_seed_matches_legacy_mapping(customers_maker):
    async with customers_maker() as s:
        for name, entity in LEGACY.items():
            assert await resolve_glpi_entity_id(s, name.upper() + " ") == entity, name
        count = (
            await s.execute(text("SELECT count(*) FROM n_infraops_customers"))
        ).scalar()
        assert count == 13


async def test_seed_is_idempotent_and_keeps_edits(customers_maker):
    from tests.conftest import SEED

    async with customers_maker() as s:
        await s.execute(
            text("UPDATE n_infraops_customers SET active=false WHERE key='tbe'")
        )
        await s.commit()
        await s.execute(text(SEED))
        await s.commit()
        assert (
            await s.execute(text("SELECT count(*) FROM n_infraops_customer_aliases"))
        ).scalar() == len(LEGACY)
        with pytest.raises(ValueError):
            await resolve_glpi_entity_id(s, "tbe")


@pytest.mark.parametrize("name", ["Outros", "unknown", "not-cavan", "", "fake-alupar"])
async def test_unknown_alias_refused(customers_maker, name):
    async with customers_maker() as s:
        assert await resolve_customer(s, name) is None
        with pytest.raises(ValueError, match="entidade"):
            await resolve_glpi_entity_id(s, name)


async def test_inactive_customer_refused(customers_maker):
    async with customers_maker() as s:
        await s.execute(
            text("UPDATE n_infraops_customers SET active=false WHERE key='cavan'")
        )
        await s.commit()
        with pytest.raises(ValueError, match="entidade"):
            await resolve_glpi_entity_id(s, "Cavan")


async def test_edit_alias_effective_next_call(api, customers_maker):
    async with api(UserRole.admin) as c:
        async with customers_maker() as s:
            assert await resolve_customer(s, "CVN") is None
        r = await c.post("/api/customers/8/aliases", json={"alias": "  CVN "})
        assert r.status_code == 201 and "cvn" in r.json()["aliases"]
        async with customers_maker() as s:
            assert await resolve_glpi_entity_id(s, "cvn") == 8
            row = (
                await s.execute(
                    text(
                        "SELECT updated_by_user_id FROM n_infraops_customers WHERE id=8"
                    )
                )
            ).scalar()
            assert row == 7
        assert (
            await c.delete("/api/customers/8/aliases", params={"alias": "CVN"})
        ).status_code == 200
        async with customers_maker() as s:
            assert await resolve_customer(s, "cvn") is None


async def test_duplicate_alias_409(api):
    async with api(UserRole.admin) as c:
        assert (
            await c.post("/api/customers/8/aliases", json={"alias": "TBE"})
        ).status_code == 409
        body = {
            "key": "novo",
            "display_name": "Novo",
            "glpi_entity_id": 20,
            "aliases": ["cavan"],
        }
        assert (await c.post("/api/customers", json=body)).status_code == 409


async def test_create_update_and_empty_name_422(api, customers_maker):
    async with api(UserRole.platform_admin) as c:
        r = await c.post(
            "/api/customers",
            json={"key": "novo", "display_name": "Novo", "glpi_entity_id": 20},
        )
        assert r.status_code == 201
        async with customers_maker() as s:
            assert await resolve_glpi_entity_id(s, "novo") == 20
        assert (
            await c.post("/api/customers", json={"key": "x", "display_name": "  "})
        ).status_code == 422
        assert (
            await c.post("/api/customers/8/aliases", json={"alias": " "})
        ).status_code == 422
        assert (
            await c.put("/api/customers/8", json={"display_name": ""})
        ).status_code == 422
        r = await c.put("/api/customers/8", json={"active": False})
        assert r.status_code == 200 and r.json()["active"] is False
        assert (
            await c.put("/api/customers/999", json={"active": False})
        ).status_code == 404


async def test_only_admin_edits(api):
    for role in (UserRole.operator, UserRole.cliente, UserRole.viewer):
        async with api(role) as c:
            assert (
                await c.post("/api/customers", json={"key": "x", "display_name": "X"})
            ).status_code == 403
            assert (
                await c.put("/api/customers/8", json={"active": False})
            ).status_code == 403
            assert (
                await c.post("/api/customers/8/aliases", json={"alias": "z"})
            ).status_code == 403
            assert (
                await c.delete("/api/customers/8/aliases", params={"alias": "cavan"})
            ).status_code == 403
    async with api(UserRole.operator) as c:
        r = await c.get("/api/customers")
        assert r.status_code == 200 and len(r.json()) == 13
    for role in (UserRole.cliente, UserRole.viewer):
        async with api(role) as c:
            assert (await c.get("/api/customers")).status_code == 403
