"""Painel por cliente contra Postgres real (pulado sem NINF_TEST_PG_URL)."""

from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routers.painel import router
from app.core.dependencies import get_current_user
from app.database import Base, get_db
from app.models.models import Asset, Incident, SocDecision, Vulnerability
from app.models.users import UserRole
from tests.conftest import URL

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def maker(customers_maker):
    engine = create_async_engine(URL)
    tabs = [
        Asset.__table__,
        Incident.__table__,
        SocDecision.__table__,
        Vulnerability.__table__,
    ]
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=tabs))
    m = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with m() as s:

        def inc(n, cliente, sev, tags, title=None, status="open"):
            return Incident(
                id=n,
                fingerprint=f"f{n}",
                title=title or f"i{n}",
                severity=sev,
                status=status,
                host_id="h",
                host_name=f"h{n}",
                trigger_id="t",
                tags={"ninf_customer_name": cliente, **tags},
            )

        s.add_all(
            [
                inc(
                    1,
                    "Cavan",
                    5,
                    {
                        "ninf_ticket_state": "opened",
                        "ninf_zabbix_status": "problem",
                        "class": "network",
                    },
                    title="FortiGate: VPN 1 X: Tunnel down",
                ),
                inc(
                    7,
                    "Cavan",
                    3,
                    {"ninf_zabbix_status": "problem", "class": "os"},
                    title="Windows: High memory utilization",
                ),
                inc(
                    8,
                    "Cavan",
                    5,
                    {"ninf_ticket_state": "opened"},
                    status="acknowledged",
                ),
                inc(
                    2, "Cavan", 3, {"ninf_ticket_state": "opened", "ninf_branch": "soc"}
                ),
                inc(3, "Cavan", 3, {}),
                inc(4, "Alupar", 5, {"ninf_ticket_state": "opened"}),
                inc(5, "Cavan", 5, {"ninf_ticket_state": "attached"}),
                inc(6, "cavan matriz", 3, {"ninf_ticket_state": "opened"}),
            ]
        )
        s.add_all(
            [
                SocDecision(
                    wazuh_rule_id="1",
                    customer_id="cavan",
                    classification="HIGH",
                    summary="x",
                    action_taken="a",
                    raw_alert={"rule": {"description": "R"}},
                ),
                SocDecision(
                    wazuh_rule_id="1",
                    customer_id="alupar",
                    classification="HIGH",
                    summary="x",
                    action_taken="a",
                ),
            ]
        )
        for cid, ag, sev in (
            ("cavan", "m1", "Critical"),
            ("cavan", "m1", "High"),
            ("alupar", "m2", "Critical"),
        ):
            s.add(
                Vulnerability(
                    source="w",
                    customer_id=cid,
                    agent=ag,
                    cve="CVE-1",
                    severity=sev,
                    raw=[],
                    loaded_at=now,
                )
            )
        await s.execute(
            text(
                "INSERT INTO n_infraops_customer_aliases(alias_norm, customer_id) "
                "SELECT 'cavan matriz', id FROM n_infraops_customers WHERE key='cavan'"
            )
        )
        s.add(
            Asset(
                zabbix_host_id="z1",
                hostname="a",
                customer_id="cavan",
                customer_name="Cavan",
            )
        )
        await s.commit()
    yield m
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
    await engine.dispose()


def _api(maker, user):
    app = FastAPI()
    app.include_router(router)

    async def db():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user] = lambda: user
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    )


async def test_operador_ve_o_cliente_pedido(maker):
    async with _api(
        maker, SimpleNamespace(id=1, role=UserRole.noc, tenant_id=None)
    ) as c:
        r = await c.get("/api/painel", params={"customer_id": "Cavan"})
    d = r.json()
    assert r.status_code == 200
    assert d["agora"] == {"noc": 3, "soc": 1, "criticos": 2}
    assert d["disponibilidade"]["fora_do_ar"] == 1
    assert d["seguranca"]["por_classe"] == {"HIGH": 1}
    assert d["seguranca"]["top_regras"] == [{"regra": "R", "total": 1}]
    assert (
        d["exposicao"]["por_severidade"]["Critical"] == 1
        and d["exposicao"]["maquinas_criticas"] == 1
    )
    assert d["exposicao"]["maquinas"] == 1
    assert d["cobertura"]["inventario"] == 1


async def test_cliente_fica_preso_ao_proprio_tenant(maker):
    cliente = SimpleNamespace(id=2, role=UserRole.cliente, tenant_id="cavan")
    async with _api(maker, cliente) as c:
        assert (await c.get("/api/painel")).json()["agora"]["noc"] == 3
        assert (
            await c.get("/api/painel", params={"customer_id": "alupar"})
        ).status_code == 403


async def test_operador_sem_cliente_e_cliente_inexistente(maker):
    async with _api(
        maker, SimpleNamespace(id=1, role=UserRole.noc, tenant_id=None)
    ) as c:
        assert (await c.get("/api/painel")).status_code == 422
        assert (
            await c.get("/api/painel", params={"customer_id": "nada"})
        ).status_code == 404
