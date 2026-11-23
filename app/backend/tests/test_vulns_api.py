"""/api/secops/vulnerabilities contra Postgres real. Pulado sem NINF_TEST_PG_URL."""

import io
import os
import zipfile
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routers.vulns import COLUMNS, router
from app.core.dependencies import require_authenticated
from app.database import Base, get_db
from app.models.models import Vulnerability
from app.models.users import UserRole

URL = os.environ.get("NINF_TEST_PG_URL")
pytestmark = [
    pytest.mark.skipif(not URL, reason="NINF_TEST_PG_URL não definido"),
    pytest.mark.asyncio,
]
NOC = SimpleNamespace(role=UserRole.noc, tenant_id=None)
RZK = SimpleNamespace(role=UserRole.viewer, tenant_id="rzk")


def vuln(customer, agent, cve, severity, cvss=None, package="pkg", eol=False):
    raw = [agent] + [None] * (len(COLUMNS) - 1)
    raw[COLUMNS.index("vulnerability.id")] = cve
    return Vulnerability(
        source="t",
        customer_id=customer,
        agent=agent,
        os="Windows 11",
        package=package,
        version="1",
        cve=cve,
        severity=severity,
        cvss=cvss,
        eol=eol,
        raw=raw,
    )


@pytest_asyncio.fixture
async def api():
    engine = create_async_engine(URL)
    t = [Vulnerability.__table__]
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=t))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=t))
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add_all(
            [
                vuln("rzk", "PC1", "CVE-1", "Critical", 9.8, package="Chrome"),
                vuln("rzk", "PC1", "CVE-2", "High", 7.5, package="100%_off"),
                vuln("rzk", "PC2", "SO-SEM-SUPORTE", "Critical", eol=True),
                vuln("target", "TGT1", "CVE-1", "Critical", 9.8),
            ]
        )
        await s.commit()

    def make(user):
        app = FastAPI()
        app.include_router(router)

        async def db():
            async with maker() as s:
                yield s

        app.dependency_overrides[get_db] = db
        app.dependency_overrides[require_authenticated] = lambda: user
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        )

    yield make
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=t))
    await engine.dispose()


async def test_noc_sees_all_and_client_only_own(api):
    async with api(NOC) as c:
        r = (await c.get("/api/secops/vulnerabilities")).json()
    assert r["total"] == 4 and r["by_severity"]["Critical"] == 3
    async with api(RZK) as c:
        r = (await c.get("/api/secops/vulnerabilities")).json()
        assert r["total"] == 3 and {x["customer_id"] for x in r["rows"]} == {"rzk"}
        assert r["agents"] == 2 and r["eol_agents"] == 1
        assert r["top_agents"][0] == {"key": "PC1", "count": 2}
        assert (
            await c.get("/api/secops/vulnerabilities?customer_id=target")
        ).status_code == 403


async def test_filters_and_like_escape(api):
    async with api(NOC) as c:
        assert (await c.get("/api/secops/vulnerabilities?cve=cve-1")).json()[
            "total"
        ] == 2
        assert (
            await c.get("/api/secops/vulnerabilities?customer_id=RZK&severity=Critical")
        ).json()["total"] == 2
        assert (await c.get("/api/secops/vulnerabilities?eol=true")).json()[
            "total"
        ] == 1
        assert (await c.get("/api/secops/vulnerabilities?package=100%25_")).json()[
            "total"
        ] == 1
        assert (await c.get("/api/secops/vulnerabilities?package=0_o")).json()[
            "total"
        ] == 0
        assert (
            await c.get("/api/secops/vulnerabilities?severity=x")
        ).status_code == 422


async def test_export_is_xlsx_in_team_layout_and_scoped(api):
    async with api(RZK) as c:
        r = await c.get("/api/secops/vulnerabilities/export")
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.content))
    sheet = z.read("xl/worksheets/sheet1.xml").decode()
    assert sheet.count("<row ") == 4  # cabeçalho + 3 da RZK
    assert "TGT1" not in sheet and "SO-SEM-SUPORTE" in sheet
    assert len(COLUMNS) == 35 and 'r="AI1"' in sheet
