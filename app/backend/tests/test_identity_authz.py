"""ADR 0015 fase A: autorização local (iss+oid -> User), sem JIT. Pulado sem NINF_TEST_PG_URL.

Ex.: NINF_TEST_PG_URL=postgresql+asyncpg://dev:dev@127.0.0.1:5439/app pytest tests/test_identity_authz.py
"""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routers.auth import router as auth_router
from app.api.routers.tenants import router as tenants_router
from app.core.jwt import create_access_token, verify_token
from app.database import Base, get_db
from app.models.users import Identity, User, UserRole

URL = os.environ.get("NINF_TEST_PG_URL")
pytestmark = [
    pytest.mark.skipif(not URL, reason="NINF_TEST_PG_URL não definido"),
    pytest.mark.asyncio,
]

HUB = "https://hub.ness.com.br"
ISS = "https://idp.example.invalid/"


@pytest_asyncio.fixture
async def maker():
    engine = create_async_engine(URL)
    tabs = [User.__table__, Identity.__table__]
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=tabs))
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
    await engine.dispose()


@pytest_asyncio.fixture
async def client(maker):
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(tenants_router, prefix="/api/tenants")

    async def _db():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_db] = _db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url=HUB
    ) as c:
        yield c


async def _user(maker, email, role=UserRole.viewer, tenant="tenant-a", **kw):
    async with maker() as s:
        u = User(email=email, hashed_password="x", role=role, tenant_id=tenant, **kw)
        s.add(u)
        await s.commit()
        return u


async def _link(maker, user, subject, issuer=ISS):
    async with maker() as s:
        s.add(Identity(issuer=issuer, subject=subject, user_id=user.id))
        await s.commit()


async def _callback(client, **claims):
    claims.setdefault("iss", ISS)
    with (
        patch(
            "app.api.routers.auth.get_settings",
            return_value=SimpleNamespace(oidc_enabled=True),
        ),
        patch(
            "app.api.routers.auth.exchange_oidc_code",
            new=AsyncMock(return_value={"id_token": "x"}),
        ),
        patch(
            "app.api.routers.auth.verify_oidc_token",
            new=AsyncMock(return_value=claims),
        ),
    ):
        return await client.post(
            "/api/auth/oidc/callback",
            headers={"Origin": HUB},
            json={"code": "c", "redirect_uri": f"{HUB}/callback"},
        )


def _bearer(user):
    token = create_access_token(
        user_id=user.id,
        role=user.role.value,
        extra_claims={"tenant_id": user.tenant_id, "session_epoch": 0},
    )
    return {"Authorization": f"Bearer {token}"}


async def _count(maker, model):
    async with maker() as s:
        return (await s.execute(select(func.count()).select_from(model))).scalar_one()


async def test_user_without_registration_gets_403_and_no_user_is_created(maker, client):
    r = await _callback(client, oid="o-1", email="ghost@example.invalid")
    assert r.status_code == 403
    assert "ghost" not in r.text
    assert "ninf_session" not in r.cookies
    assert await _count(maker, User) == 0


async def test_inactive_user_gets_401(maker, client):
    u = await _user(maker, "a@example.invalid", is_active=False)
    await _link(maker, u, "o-1")
    r = await _callback(client, oid="o-1")
    assert r.status_code == 401
    assert "ninf_session" not in r.cookies


async def test_login_uses_sub_when_idp_has_no_oid(maker, client):
    u = await _user(maker, "a@example.invalid")
    await _link(maker, u, "sub-1")
    r = await _callback(client, sub="sub-1")
    assert r.status_code == 200 and r.json()["id"] == u.id


async def test_same_issuer_and_oid_with_changed_email_is_same_user(maker, client):
    a = await _user(maker, "a@example.invalid")
    b = await _user(maker, "b@example.invalid", role=UserRole.admin)
    await _link(maker, a, "o-1")
    r = await _callback(client, oid="o-1", email="b@example.invalid")
    assert r.status_code == 200
    assert r.json()["id"] == a.id and r.json()["email"] == "a@example.invalid"
    assert b.id != a.id


async def test_email_of_existing_user_with_new_oid_gets_403(maker, client):
    a = await _user(maker, "a@example.invalid", role=UserRole.platform_admin)
    await _link(maker, a, "o-1")
    r = await _callback(client, oid="o-NEW", email="a@example.invalid")
    assert r.status_code == 403
    assert "ninf_session" not in r.cookies


async def test_same_oid_from_another_issuer_gets_403(maker, client):
    a = await _user(maker, "a@example.invalid")
    await _link(maker, a, "o-1")
    r = await _callback(client, oid="o-1", iss="https://other.example.invalid/")
    assert r.status_code == 403


async def test_forged_groups_role_and_tenant_claims_are_ignored(maker, client):
    u = await _user(maker, "a@example.invalid", UserRole.viewer, "tenant-a")
    await _link(maker, u, "o-1")
    r = await _callback(
        client,
        oid="o-1",
        groups=["platform_admin", "ness-os-platform-admin"],
        role="platform_admin",
        tenant_id="tenant-b",
    )
    assert r.status_code == 200 and r.json()["role"] == "viewer"
    async with maker() as s:
        fresh = await s.get(User, u.id)
        assert (fresh.role, fresh.tenant_id) == (UserRole.viewer, "tenant-a")
    # a sessão emitida carrega papel e tenant do banco, não os forjados
    payload = verify_token(r.cookies["ninf_session"])
    assert (payload["role"], payload["tenant_id"]) == ("viewer", "tenant-a")
    other = await client.get("/api/tenants/tenant-b/summary", headers={"Origin": HUB})
    assert other.status_code == 403


async def test_tenant_user_cannot_access_another_tenant(maker, client):
    u = await _user(maker, "a@example.invalid", UserRole.cliente, "tenant-a")
    r = await client.get("/api/tenants/tenant-b/summary", headers=_bearer(u))
    assert r.status_code == 403


async def test_only_platform_admin_can_register_identity(maker, client):
    target = await _user(maker, "t@example.invalid")
    for role in (UserRole.admin, UserRole.operator, UserRole.noc):
        caller = await _user(maker, f"{role.value}@example.invalid", role, None)
        r = await client.post(
            "/api/auth/identities",
            headers=_bearer(caller),
            json={"user_id": target.id, "issuer": ISS, "subject": "o-1"},
        )
        assert r.status_code == 403, role
    assert await _count(maker, Identity) == 0


async def test_register_identity_then_login_and_duplicate_is_409(maker, client):
    pa = await _user(maker, "pa@example.invalid", UserRole.platform_admin, None)
    target = await _user(maker, "t@example.invalid")
    body = {"user_id": target.id, "issuer": ISS, "subject": "o-1"}
    r = await client.post("/api/auth/identities", headers=_bearer(pa), json=body)
    assert r.status_code == 201
    async with maker() as s:
        row = (await s.execute(select(Identity))).scalar_one()
        assert row.created_by_user_id == pa.id and row.created_at is not None
    assert (await _callback(client, oid="o-1")).json()["id"] == target.id

    other = await _user(maker, "o@example.invalid")
    for b in (body, {**body, "user_id": other.id}):
        r = await client.post("/api/auth/identities", headers=_bearer(pa), json=b)
        assert r.status_code == 409
    assert await _count(maker, Identity) == 1


async def test_register_identity_for_unknown_user_is_404(maker, client):
    pa = await _user(maker, "pa@example.invalid", UserRole.platform_admin, None)
    r = await client.post(
        "/api/auth/identities",
        headers=_bearer(pa),
        json={"user_id": 999, "issuer": ISS, "subject": "o-1"},
    )
    assert r.status_code == 404
