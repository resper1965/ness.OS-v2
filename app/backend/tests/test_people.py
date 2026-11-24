"""Cadastro de pessoas e equipes contra Postgres real (pulado sem NINF_TEST_PG_URL)."""

from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from app.api.routers import people
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import User, UserRole

pytestmark = pytest.mark.asyncio


@pytest.fixture
def api(people_maker, monkeypatch):
    monkeypatch.setattr(people, "_kick", lambda: None)

    def make(role=UserRole.admin):
        app = FastAPI()
        app.include_router(people.router)

        async def db():
            async with people_maker() as s:
                yield s

        app.dependency_overrides[get_db] = db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=7, role=role
        )
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        )

    return make


async def _cid(people_maker, key):
    from app.models import Customer

    async with people_maker() as s:
        return (
            await s.execute(select(Customer.id).where(Customer.key == key))
        ).scalar_one()


async def test_externo_requires_exactly_one_customer(api, people_maker):
    a, b = await _cid(people_maker, "cavan"), await _cid(people_maker, "tbe")
    async with api() as c:
        for ids in ([], [a, b]):
            r = await c.post(
                "/api/people",
                json={
                    "email": "x@c.com",
                    "full_name": "X",
                    "kind": "externo",
                    "customer_ids": ids,
                },
            )
            assert r.status_code == 422


async def test_externo_cannot_be_oncall(api, people_maker):
    a = await _cid(people_maker, "cavan")
    async with api() as c:
        r = await c.post(
            "/api/people",
            json={
                "email": "x@c.com",
                "full_name": "X",
                "kind": "externo",
                "customer_ids": [a],
                "is_oncall": True,
            },
        )
        assert r.status_code == 422


async def test_externo_gets_cliente_role_and_tenant(api, people_maker):
    a = await _cid(people_maker, "cavan")
    async with api() as c:
        r = await c.post(
            "/api/people",
            json={
                "email": "Elid@Cavan.com",
                "full_name": "E",
                "kind": "externo",
                "customer_ids": [a],
            },
        )
        assert r.status_code == 201
        assert r.json()["email"] == "elid@cavan.com" and r.json()["role"] == "cliente"
        dup = await c.post(
            "/api/people",
            json={"email": "elid@cavan.com", "full_name": "E", "kind": "ness"},
        )
        assert dup.status_code == 409
    async with people_maker() as s:
        assert (await s.execute(select(User))).scalar_one().tenant_id == "cavan"


async def test_only_admin_manages_people(people_maker):
    from app.core.dependencies import require_admin

    for role in (UserRole.noc, UserRole.cliente, UserRole.operator):
        with pytest.raises(Exception) as e:
            require_admin(SimpleNamespace(role=role))
        assert e.value.status_code == 403
    deps = {d.call for r in people.router.routes for d in r.dependant.dependencies}
    assert deps == {require_admin, get_db}


async def test_delete_deactivates_and_bumps_session_epoch(api, people_maker):
    async with api() as c:
        pid = (
            await c.post(
                "/api/people",
                json={
                    "email": "a@ness.com.br",
                    "full_name": "A",
                    "kind": "ness",
                    "is_oncall": True,
                },
            )
        ).json()["id"]
        r = await c.delete(f"/api/people/{pid}")
        assert (
            r.status_code == 200
            and r.json()["is_active"] is False
            and r.json()["is_oncall"] is False
        )
    async with people_maker() as s:
        assert (await s.get(User, pid)).session_epoch == 1


async def test_same_local_part_is_rejected_because_glpi_login_would_collide(api):
    async with api() as c:
        assert (
            await c.post(
                "/api/people",
                json={"email": "alex@ness.com.br", "full_name": "A", "kind": "ness"},
            )
        ).status_code == 201
        r = await c.post(
            "/api/people",
            json={"email": "alex@cliente.com", "full_name": "B", "kind": "ness"},
        )
        assert r.status_code == 409


async def test_inactive_customer_is_rejected(api, people_maker):
    from sqlalchemy import update

    from app.models import Customer

    a = await _cid(people_maker, "cavan")
    async with people_maker() as s:
        await s.execute(update(Customer).where(Customer.id == a).values(active=False))
        await s.commit()
    async with api() as c:
        r = await c.post(
            "/api/people",
            json={
                "email": "x@c.com",
                "full_name": "X",
                "kind": "externo",
                "customer_ids": [a],
            },
        )
        assert r.status_code == 422


async def test_admin_cannot_deactivate_self_through_update(api):
    async with api() as c:
        assert (
            await c.put("/api/people/7", json={"is_active": False})
        ).status_code in (404, 409)


async def test_malformed_email_is_rejected(api):
    async with api() as c:
        for bad in ("ana@", "ana@@ness.com", "@ness.com", "sem-arroba"):
            r = await c.post(
                "/api/people", json={"email": bad, "full_name": "A", "kind": "ness"}
            )
            assert r.status_code == 422, bad


async def test_local_admin_cannot_touch_platform_admin(api, people_maker):
    async with people_maker() as s:
        s.add(
            User(
                email="pa@ness.com.br",
                hashed_password="x",
                role=UserRole.platform_admin,
            )
        )
        await s.commit()
        pid = (
            await s.execute(select(User.id).where(User.email == "pa@ness.com.br"))
        ).scalar_one()
    async with api(UserRole.admin) as c:
        assert (
            await c.put(f"/api/people/{pid}", json={"is_active": False})
        ).status_code == 403
        assert (await c.delete(f"/api/people/{pid}")).status_code == 403
    async with api(UserRole.platform_admin) as c:
        assert (await c.delete(f"/api/people/{pid}")).status_code == 200


async def test_underscore_in_login_is_not_a_wildcard(api):
    async with api() as c:
        assert (
            await c.post(
                "/api/people",
                json={"email": "anax1@a.com", "full_name": "A", "kind": "ness"},
            )
        ).status_code == 201
        assert (
            await c.post(
                "/api/people",
                json={"email": "ana_1@b.com", "full_name": "B", "kind": "ness"},
            )
        ).status_code == 201


async def test_role_without_operational_access_cannot_join_a_team(api, people_maker):
    cid = await _cid(people_maker, "cavan")
    async with people_maker() as s:
        s.add(User(email="v@ness.com.br", hashed_password="x", role=UserRole.viewer))
        await s.commit()
        vid = (
            await s.execute(select(User.id).where(User.email == "v@ness.com.br"))
        ).scalar_one()
    async with api() as c:
        assert (
            await c.put(f"/api/people/{vid}", json={"customer_ids": [cid]})
        ).status_code == 422
