"""Real public code exchange, JWT verification, JIT, RBAC and cleanup of test users."""

import asyncio
import json
from pathlib import Path

import httpx
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models.users import User, UserRole


async def main():
    rows = json.loads(Path("/tmp/ness-hub-oidc-fixtures.json").read_text())
    emails = [r["email"] for r in rows]
    results = []
    base = "https://hub.ness.com.br"
    try:
        disabled = next(r for r in rows if r["label"] == "disabled")
        async with SessionLocal() as db:
            db.add(
                User(
                    email=disabled["email"],
                    full_name="Temporary disabled check",
                    hashed_password="!",
                    role=UserRole.cliente,
                    tenant_id="alupar",
                    is_active=False,
                )
            )
            await db.commit()
        for row in rows:
            async with httpx.AsyncClient(
                base_url=base, timeout=30, headers={"Origin": base}
            ) as client:
                body = {
                    "code": row["codes"][0],
                    "redirect_uri": base + "/callback",
                    "code_verifier": row["verifier"],
                }
                response = await client.post("/api/auth/oidc/callback", json=body)
                expected = 403 if row["label"] in ("disabled", "unassigned") else 200
                assert response.status_code == expected, (
                    row["label"],
                    response.status_code,
                    response.text,
                )
                if expected == 403:
                    assert not response.cookies
                    results.append({"case": row["label"], "status": 403})
                    continue
                assert response.json()["role"] == (
                    "noc" if row["label"] == "operator" else "cliente"
                )
                assert "httponly" in response.headers["set-cookie"].lower()
                assert (await client.get("/api/auth/me")).status_code == 200
                data = (await client.get("/api/incidents?limit=100")).json()[
                    "incidents"
                ]
                if row["label"] != "operator":
                    assert all(i["client"].lower() == row["tenant"] for i in data)
                    other = "alupar" if row["tenant"] == "cavan" else "cavan"
                    assert (
                        await client.get("/api/incidents", params={"tenant_id": other})
                    ).status_code == 403
                else:
                    assert (
                        await client.get("/api/dashboard/pipeline-status")
                    ).status_code == 200
                async with SessionLocal() as db:
                    stored = (
                        await db.scalars(select(User).where(User.email == row["email"]))
                    ).one()
                    assert stored.tenant_id == row["tenant"]
                assert (await client.post("/api/auth/logout")).status_code == 204
                assert (await client.get("/api/auth/me")).status_code == 401
                replay = await client.post("/api/auth/oidc/callback", json=body)
                assert replay.status_code == 400 and not replay.cookies
                body.update(
                    code=row["codes"][1], code_verifier="wrong-verifier-" + "a" * 50
                )
                wrong = await client.post("/api/auth/oidc/callback", json=body)
                assert wrong.status_code == 400 and not wrong.cookies
                results.append(
                    {
                        "case": row["label"],
                        "status": 200,
                        "code_replay": 400,
                        "wrong_pkce": 400,
                        "incidents": len(data),
                        "tenant_persisted": True,
                    }
                )
    finally:
        async with SessionLocal() as db:
            await db.execute(delete(User).where(User.email.in_(emails)))
            await db.commit()
            assert not (
                await db.scalars(select(User.id).where(User.email.in_(emails)))
            ).all()
    print(
        json.dumps(
            {
                "status": "ok",
                "cases": results,
                "hub_test_users_removed": True,
                "interactive_login_mfa": "not_tested",
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
