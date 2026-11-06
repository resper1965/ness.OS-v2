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
from app.services.customers import (
    AmbiguousCustomer,
    resolve_active_customer,
    resolve_customer,
    resolve_glpi_entity_id,
)
from app.workers import alerts

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


# Strings gravadas em produção (tags.ninf_customer_name e lower() em assets.customer_id).
LEGACY_DISPLAY = {
    "alupar": "Alupar", "tbe": "TBE", "target": "Target", "ltb": "LTB",
    "alupar-pe": "Alupar PE", "alupar-co": "Alupar CO", "bichara": "Bichara",
    "cavan": "Cavan", "nova-energia": "Nova Energia", "numen": "Numen IT",
    "tne": "TNE", "unimed": "Unimed", "ness": "Ness",
}  # fmt: skip


async def test_seed_display_names_match_legacy_identity(customers_maker):
    async with customers_maker() as s:
        rows = (
            await s.execute(text("SELECT key, display_name FROM n_infraops_customers"))
        ).all()
    assert dict(rows) == LEGACY_DISPLAY
    assert {d.lower() for d in LEGACY_DISPLAY.values()} == {
        "alupar", "tbe", "target", "ltb", "alupar pe", "alupar co", "bichara",
        "cavan", "nova energia", "numen it", "tne", "unimed", "ness",
    }  # fmt: skip


async def test_aliases_of_same_customer_store_same_identity(
    customers_maker, monkeypatch
):
    monkeypatch.setattr(alerts, "SessionLocal", customers_maker)
    for names, expected in (
        (("Alupar Investimento S.A.", " ALUPAR ", "alupar"), ("Alupar", 1)),
        (("numen", "NUMEN IT", "Numen It"), ("Numen IT", 10)),
        (("NESS", "ness processos e tecnologia ltda."), ("Ness", 0)),
    ):
        for name in names:
            assert await alerts.canonical_customer(name) == expected, name


async def test_hostgroup_returns_canonical_name(customers_maker):
    async with customers_maker() as s:
        got = await alerts.customer_from_hostgroups(s, [{"name": "[ numen ]"}])
        assert got == "Numen IT"


async def test_resolver_matches_display_name_and_key_without_alias_row(
    customers_maker,
):
    async with customers_maker() as s:
        await s.execute(text("DELETE FROM n_infraops_customer_aliases"))
        await s.commit()
        assert await resolve_glpi_entity_id(s, "Numen IT") == 10
        assert await resolve_glpi_entity_id(s, " Nova-Energia ") == 9
        assert await resolve_glpi_entity_id(s, "Alupar PE") == 5


async def test_delete_secondary_alias_keeps_old_tickets_resolving(api, customers_maker):
    async with api(UserRole.admin) as c:
        assert (
            await c.post("/api/customers/8/aliases", json={"alias": "cvn"})
        ).status_code == 201
        assert (
            await c.delete("/api/customers/8/aliases", params={"alias": "CVN"})
        ).status_code == 200
        async with customers_maker() as s:
            assert await resolve_glpi_entity_id(s, "Cavan") == 8
            assert await resolve_customer(s, "cvn") is None


async def test_delete_canonical_alias_is_422(api, customers_maker):
    async with api(UserRole.admin) as c:
        for alias in ("cavan", "Cavan ", "nova energia", "nova-energia", "numen it"):
            r = await c.delete(
                "/api/customers/{}/aliases".format(
                    8 if "cavan" in alias.lower() else 9 if "nova" in alias else 10
                ),
                params={"alias": alias},
            )
            assert r.status_code == 422, alias
        assert (
            await c.delete("/api/customers/9/aliases", params={"alias": "novaenergia"})
        ).status_code == 200


async def test_alias_owned_by_other_customer_is_409(api, customers_maker):
    async with api(UserRole.admin) as c:
        assert (
            await c.post("/api/customers/8/aliases", json={"alias": "TBE"})
        ).status_code == 409
        # display_name/key de outro cliente também é dele, mesmo sem linha de alias
        async with customers_maker() as s:
            await s.execute(
                text("DELETE FROM n_infraops_customer_aliases WHERE customer_id=10")
            )
            await s.commit()
        for alias in ("Numen IT", "numen"):
            r = await c.post("/api/customers/8/aliases", json={"alias": alias})
            assert r.status_code == 409, alias
        r = await c.put("/api/customers/8", json={"display_name": "tbe"})
        assert r.status_code == 409


async def test_ambiguous_name_is_refused_not_picked(customers_maker):
    async with customers_maker() as s:
        await s.execute(
            text(
                "UPDATE n_infraops_customer_aliases SET customer_id=8 WHERE alias_norm='numen it'"
            )
        )
        await s.commit()
        with pytest.raises(AmbiguousCustomer):
            await resolve_customer(s, "numen it")
        with pytest.raises(AmbiguousCustomer):
            await alerts.customer_from_hostgroups(s, [{"name": "[ Numen IT ]"}])


async def test_active_entity_is_unique(api, customers_maker):
    async with api(UserRole.admin) as c:
        body = {"key": "dup", "display_name": "Dup", "glpi_entity_id": 8}
        assert (await c.post("/api/customers", json=body)).status_code == 409
        r = await c.post("/api/customers", json={**body, "active": False})
        assert r.status_code == 201
        new_id = r.json()["id"]
        assert (
            await c.put(f"/api/customers/{new_id}", json={"active": True})
        ).status_code == 409
        assert (
            await c.put("/api/customers/3", json={"glpi_entity_id": 8})
        ).status_code == 409
        # desativar o dono libera a entidade
        assert (
            await c.put("/api/customers/8", json={"active": False})
        ).status_code == 200
        assert (
            await c.put(f"/api/customers/{new_id}", json={"active": True})
        ).status_code == 200


async def test_db_rejects_two_active_customers_on_same_entity(customers_maker):
    from sqlalchemy.exc import IntegrityError

    async with customers_maker() as s:
        with pytest.raises(IntegrityError):
            await s.execute(
                text(
                    "INSERT INTO n_infraops_customers (key, display_name, glpi_entity_id)"
                    " VALUES ('x', 'X', 8)"
                )
            )


async def test_hostgroups_same_entity_different_customers_is_ambiguous(
    monkeypatch, customers_maker
):
    fakes = {
        "[ A ]": SimpleNamespace(id=1, glpi_entity_id=5, display_name="A"),
        "[ B ]": SimpleNamespace(id=2, glpi_entity_id=5, display_name="B"),
    }

    async def fake(_s, name):
        return fakes[f"[ {name} ]"]

    monkeypatch.setattr(alerts, "resolve_active_customer", fake)
    async with customers_maker() as s:
        with pytest.raises(ValueError, match="distintos"):
            await alerts.customer_from_hostgroups(
                s, [{"name": "[ A ]"}, {"name": "[ B ]"}]
            )


async def test_resolve_active_customer_returns_canonical(customers_maker):
    async with customers_maker() as s:
        c = await resolve_active_customer(s, "ALUPAR-CO")
        assert (c.display_name, c.glpi_entity_id) == ("Alupar CO", 6)


async def test_rename_keeps_old_and_new_name_resolving(api, customers_maker):
    async with api(UserRole.admin) as c:
        r = await c.put("/api/customers/8", json={"display_name": "Cavan SA"})
        assert r.status_code == 200
        async with customers_maker() as s:
            assert await resolve_glpi_entity_id(s, "Cavan") == 8
            assert await resolve_glpi_entity_id(s, "cavan sa") == 8


async def test_hostgroup_bracket_resolves(customers_maker):
    async with customers_maker() as s:
        assert (
            await alerts.customer_from_hostgroups(s, [{"name": "[ TBE ] [ X ]"}])
            == "TBE"
        )


async def test_zabbix_servers_is_ness(customers_maker):
    async with customers_maker() as s:
        for name in ("Zabbix servers", "UAT sintético"):
            assert await alerts.customer_from_hostgroups(s, [{"name": name}]) == "Ness"


async def test_alupar_with_pe_prefers_pe(customers_maker):
    async with customers_maker() as s:
        for child in ("Alupar PE", "Alupar CO"):
            got = await alerts.customer_from_hostgroups(
                s, [{"name": "[ Alupar ]"}, {"name": f"[ {child} ]"}]
            )
            assert got == child
        assert (
            await alerts.customer_from_hostgroups(s, [{"name": "[ Alupar ]"}])
            == "Alupar"
        )


async def test_ambiguous_raises(customers_maker):
    async with customers_maker() as s:
        msg = "Host associado a clientes distintos; ticket recusado"
        for groups in (
            [{"name": "[ Cavan ]"}, {"name": "[ TBE ]"}],
            [{"name": "[ Alupar PE ]"}, {"name": "[ Alupar CO ]"}],
            [{"name": "[ Alupar ]"}, {"name": "[ Alupar PE ]"}, {"name": "[ TBE ]"}],
        ):
            with pytest.raises(ValueError) as e:
                await alerts.customer_from_hostgroups(s, groups)
            assert str(e.value) == msg
        assert (
            await alerts.customer_from_hostgroups(s, [{"name": "Linux servers"}])
            is None
        )


async def test_hostgroup_rule_edit_effective_next_call(customers_maker):
    async with customers_maker() as s:
        assert await alerts.customer_from_hostgroups(s, [{"name": "Grupo TBE"}]) is None
        await s.execute(
            text(
                "INSERT INTO n_infraops_hostgroup_rules (pattern, customer_id) "
                "SELECT 'Grupo TBE', id FROM n_infraops_customers WHERE key='tbe'"
            )
        )
        await s.commit()
        assert (
            await alerts.customer_from_hostgroups(s, [{"name": "Grupo TBE"}]) == "TBE"
        )


async def test_db_rejects_empty_pattern_and_self_ignore(customers_maker):
    from sqlalchemy.exc import IntegrityError

    for values in ("'  ', 8, NULL", "NULL, 8, 8", "'', 8, NULL"):
        async with customers_maker() as s:
            with pytest.raises(IntegrityError):
                await s.execute(
                    text(
                        "INSERT INTO n_infraops_hostgroup_rules "
                        f"(pattern, customer_id, ignore_when_with_customer_id) VALUES ({values})"
                    )
                )


async def test_rule_to_inactive_customer_is_dropped_not_fallback(customers_maker):
    async with customers_maker() as s:
        await s.execute(
            text("UPDATE n_infraops_customers SET active=false WHERE key='ness'")
        )
        await s.commit()
        # a regra cadastrada vence o padrão: sem fallback para outro cliente
        assert (
            await alerts.customer_from_hostgroups(s, [{"name": "Zabbix servers"}])
            is None
        )
        got = await alerts.customer_from_hostgroups(
            s, [{"name": "Zabbix servers"}, {"name": "[ TBE ]"}]
        )
        assert got == "TBE"
