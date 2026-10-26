"""Exercise real public login/RBAC using disposable accounts, removed in finally."""
import asyncio
import json
import secrets

import httpx
from sqlalchemy import delete, select

from app.api.routers.auth import _hash_password
from app.core.jwt import create_access_token
from app.database import SessionLocal
from app.models import User, UserRole


async def main():
    created = []
    results = []
    base = "https://hub.ness.com.br"
    try:
        for role, tenant in [(UserRole.cliente, "alupar"), (UserRole.cliente, "cavan"), (UserRole.noc, None)]:
            password = secrets.token_urlsafe(32)
            async with SessionLocal() as session:
                user = User(email=f"validation-{secrets.token_hex(8)}@ness.invalid", hashed_password=_hash_password(password),
                            role=role, tenant_id=tenant, full_name="Temporary deployment validation", is_active=True)
                session.add(user)
                await session.commit()
                created.append(user.id)
            async with httpx.AsyncClient(base_url=base, timeout=40, headers={"Origin": base}) as client:
                login = await client.post("/api/auth/login", json={"email": user.email, "password": password})
                assert login.status_code == 200, ("login", login.status_code)
                cookie = login.headers["set-cookie"].lower()
                assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie
                assert (await client.get("/api/auth/me")).status_code == 200
                incidents = await client.get("/api/incidents?limit=100")
                assert incidents.status_code == 200, ("incidents", incidents.status_code)
                data = incidents.json()["incidents"]
                cmdb = await client.get("/api/assets/cmdb?limit=500")
                assert cmdb.status_code == 200
                if tenant:
                    assert all(i["client"].lower() == tenant for i in data)
                    assert all(i["client"].lower() == tenant for i in cmdb.json()["items"])
                    other = "cavan" if tenant == "alupar" else "alupar"
                    assert (await client.get(f"/api/incidents?tenant_id={other}")).status_code == 403
                    assert (await client.get(f"/api/assets/cmdb?tenant_id={other}")).status_code == 403
                    assert (await client.get("/api/dashboard/pipeline-status")).status_code == 403
                    # A forged role claim cannot override the persisted role.
                    forged = create_access_token(user.id, "admin")
                    assert (await client.get("/api/dashboard/pipeline-status", headers={"Authorization": f"Bearer {forged}"})).status_code == 403
                else:
                    assert (await client.get("/api/dashboard/pipeline-status")).status_code == 200
                expired = create_access_token(user.id, role.value, expire_hours=-1)
                assert (await client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})).status_code == 401
                assert (await client.post("/api/auth/logout")).status_code == 204
                assert (await client.get("/api/auth/me")).status_code == 401
                bad = await client.post("/api/auth/login", json={"email": user.email, "password": "wrong"})
                assert bad.status_code == 401
                async with SessionLocal() as session:
                    stored = await session.get(User, user.id)
                    stored.is_active = False
                    await session.commit()
                disabled = await client.post("/api/auth/login", json={"email": user.email, "password": password})
                assert disabled.status_code == 403
                token = create_access_token(user.id, role.value)
                assert (await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401
                results.append({"role": role.value, "tenant": tenant, "incidents": len(data),
                                "cmdb_assets": cmdb.json()["total"], "checks": "passed"})
    finally:
        if created:
            async with SessionLocal() as session:
                await session.execute(delete(User).where(User.id.in_(created), User.email.like("validation-%@ness.invalid")))
                await session.commit()
                remaining = (await session.execute(select(User.id).where(User.id.in_(created)))).scalars().all()
                assert not remaining, "Temporary accounts not removed"
        print(json.dumps({"results": results, "temporary_accounts_removed": len(created)}))


asyncio.run(main())
