"""Contatos de aviso do cliente contra Postgres real (pulado sem NINF_TEST_PG_URL)."""

import logging
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from app.api.routers.customer_contacts import router
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.users import UserRole

pytestmark = pytest.mark.asyncio

EMAIL, PHONE = "plantao.secreto@cliente.example", "+55 11 99999-0000"
BODY = {
    "name": "Plantão",
    "email": EMAIL,
    "phone": PHONE,
    "role": "plantao",
    "notify_severity_min": 3,
}


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
            id=7, role=role, tenant_id=None
        )
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        )

    return make


async def test_contact_crud(api):
    async with api(UserRole.admin) as c:
        r = await c.post("/api/customers/8/contacts", json=BODY)
        assert r.status_code == 201 and r.json()["email"] == EMAIL
        cid = r.json()["id"]
        r = await c.put(
            f"/api/customers/8/contacts/{cid}", json={"phone": None, "active": False}
        )
        assert (
            r.status_code == 200
            and r.json()["phone"] is None
            and not r.json()["active"]
        )
        assert len((await c.get("/api/customers/8/contacts")).json()) == 1
        assert (await c.get("/api/customers/9/contacts")).json() == []
        assert (
            await c.put(f"/api/customers/9/contacts/{cid}", json={"name": "x"})
        ).status_code == 404
        assert (await c.delete(f"/api/customers/8/contacts/{cid}")).status_code == 204
        assert (await c.get("/api/customers/8/contacts")).json() == []
        assert (
            await c.post("/api/customers/999/contacts", json=BODY)
        ).status_code == 404


@pytest.mark.parametrize(
    "patch",
    [{"email": "sem-arroba"}, {"email": ""}, {"notify_severity_min": 0},
     {"notify_severity_min": 6}, {"name": " "}],
)  # fmt: skip
async def test_email_validated_422(api, patch):
    async with api(UserRole.admin) as c:
        r = await c.post("/api/customers/8/contacts", json={**BODY, **patch})
        assert r.status_code == 422
        assert (await c.get("/api/customers/8/contacts")).json() == []


async def test_client_role_403(api):
    async with api(UserRole.admin) as c:
        cid = (await c.post("/api/customers/8/contacts", json=BODY)).json()["id"]
    for role in (UserRole.viewer, UserRole.helpdesk, UserRole.operator):
        async with api(role) as c:
            assert (await c.get("/api/customers/8/contacts")).status_code == 403
            assert (
                await c.post("/api/customers/8/contacts", json=BODY)
            ).status_code == 403
    for role in (UserRole.noc, UserRole.soc):
        async with api(role) as c:
            assert (await c.get("/api/customers/8/contacts")).status_code == 200
            assert (
                await c.put(f"/api/customers/8/contacts/{cid}", json={"name": "x"})
            ).status_code == 403
            assert (
                await c.delete(f"/api/customers/8/contacts/{cid}")
            ).status_code == 403
    async with api(UserRole.platform_admin) as c:
        assert (await c.get("/api/customers/8/contacts")).status_code == 200


async def test_contact_not_logged_in_audit(api, caplog):
    caplog.set_level(logging.DEBUG)
    async with api(UserRole.admin) as c:
        cid = (await c.post("/api/customers/8/contacts", json=BODY)).json()["id"]
        await c.put(
            f"/api/customers/8/contacts/{cid}",
            json={
                "email": "novo.secreto@cliente.example",
                "phone": "+55 21 98888-1111",
            },
        )
        await c.delete(f"/api/customers/8/contacts/{cid}")
    logs = caplog.text
    assert "customer_contact_updated" in logs and "fields=['email', 'phone']" in logs
    for secret in (EMAIL, PHONE, "novo.secreto", "98888"):
        assert secret not in logs


@pytest.mark.parametrize(
    "patch",
    [{"name": "n" * 256}, {"phone": "9" * 65}, {"role": "r" * 65},
     {"email": "a" * 310 + "@x.example"}],
)  # fmt: skip
async def test_oversize_input_is_422(api, patch):
    async with api(UserRole.admin) as c:
        assert (
            await c.post("/api/customers/8/contacts", json={**BODY, **patch})
        ).status_code == 422
        cid = (await c.post("/api/customers/8/contacts", json=BODY)).json()["id"]
        assert (
            await c.put(f"/api/customers/8/contacts/{cid}", json=patch)
        ).status_code == 422


async def test_db_error_does_not_leak_email_or_phone(api, customers_maker, caplog):
    async with (
        customers_maker() as s
    ):  # força erro de banco com DETAIL "Failing row contains (...)"
        await s.execute(
            text(
                "ALTER TABLE n_infraops_customer_contacts ADD CONSTRAINT ck_x "
                f"CHECK (email <> '{EMAIL}')"
            )
        )
        await s.commit()
    caplog.set_level(logging.DEBUG)
    async with api(UserRole.admin) as c:
        r = await c.post("/api/customers/8/contacts", json=BODY)
    assert r.status_code == 500
    for out in (r.text, caplog.text):
        assert EMAIL not in out and PHONE not in out
    assert "customer_contact_db_error" in caplog.text


async def test_engine_hides_sql_parameters():
    from app.database import engine

    assert engine.sync_engine.hide_parameters is True
