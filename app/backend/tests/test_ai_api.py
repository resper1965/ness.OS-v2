"""/api/ai contra Postgres real. Pulado sem NINF_TEST_PG_URL."""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routers.ai import router
from app.core.dependencies import require_noc
from app.database import Base, get_db
from app.models.models import (
    AIDecision,
    Asset,
    Customer,
    CustomerAlias,
    Incident,
    PlatformParam,
)
from app.models.users import UserRole

URL = os.environ.get("NINF_TEST_PG_URL")
pytestmark = [
    pytest.mark.skipif(not URL, reason="NINF_TEST_PG_URL não definido"),
    pytest.mark.asyncio,
]
TABLES = [
    Customer.__table__,
    CustomerAlias.__table__,
    PlatformParam.__table__,
    Asset.__table__,
    Incident.__table__,
    AIDecision.__table__,
]
NOW = datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def maker():
    engine = create_async_engine(URL)
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=TABLES))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=TABLES))
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=TABLES))
    await engine.dispose()


@pytest.fixture
def api(maker):
    def make(user):
        app = FastAPI()
        app.include_router(router)

        async def db():
            async with maker() as s:
                yield s

        app.dependency_overrides[get_db] = db
        app.dependency_overrides[require_noc] = lambda: user
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        )

    return make


NOC = SimpleNamespace(id=1, role=UserRole.noc, tenant_id=None)


def _row(n, customer="acme", **kw):
    return AIDecision(
        kind=kw.pop("kind", "incident_analysis"),
        customer_id=customer,
        source_ref=f"r{n}",
        outcome=kw.pop("outcome", "ok"),
        prompt_version="v",
        **kw,
    )


async def _seed(maker, *rows):
    async with maker() as s:
        s.add_all(rows)
        await s.commit()
        return [r.id for r in rows]


async def test_feedback_cross_tenant_is_404(api, maker):
    [i] = await _seed(maker, _row(1, "acme"))
    other = SimpleNamespace(id=2, role=UserRole.cliente, tenant_id="other")
    async with api(other) as c:
        r = await c.post(f"/api/ai/decisions/{i}/feedback", json={"verdict": "wrong"})
    assert r.status_code == 404
    mine = SimpleNamespace(id=2, role=UserRole.cliente, tenant_id="ACME")
    async with api(mine) as c:
        r = await c.post(f"/api/ai/decisions/{i}/feedback", json={"verdict": "wrong"})
    assert r.status_code == 200


async def test_feedback_overwrites(api, maker):
    [i] = await _seed(maker, _row(1))
    async with api(NOC) as c:
        url = f"/api/ai/decisions/{i}/feedback"
        assert (await c.post(url, json={"verdict": "useful"})).status_code == 200
        assert (await c.post(url, json={"verdict": "x"})).status_code == 422
        async with api(SimpleNamespace(id=9, role=UserRole.soc, tenant_id=None)) as c2:
            assert (await c2.post(url, json={"verdict": "wrong"})).status_code == 200
        assert (await c.get("/api/ai/decisions")).json()[0]["feedback"] == "wrong"
    async with maker() as s:
        d = await s.get(AIDecision, i)
    assert (d.feedback, d.feedback_user_id) == ("wrong", 9) and d.feedback_at


async def test_decisions_list_filters_and_hides_payload(api, maker):
    await _seed(
        maker,
        _row(1, divergent=True, request={"x": 1}),
        _row(2, "beta", kind="soc_triage"),
    )
    async with api(NOC) as c:
        assert len((await c.get("/api/ai/decisions")).json()) == 2
        rows = (await c.get("/api/ai/decisions?divergent=true")).json()
        assert [r["customer_id"] for r in rows] == ["acme"]
        assert "request" not in rows[0] and "response" not in rows[0]
        rows = (
            await c.get("/api/ai/decisions?kind=soc_triage&customer_id=beta")
        ).json()
        assert len(rows) == 1


async def test_metrics_rates_and_null_cost(api, maker):
    await _seed(
        maker,
        _row(1, divergent=True, cost_usd=0.5, latency_ms=100, feedback="useful"),
        _row(2, outcome="error", cost_usd=0.25, latency_ms=300),
        _row(3, cost_usd=None, feedback="wrong"),
        _row(4, cost_usd=0.25, feedback="unread"),
    )
    async with api(NOC) as c:
        r = await c.get("/api/ai/metrics")
    k = r.json()["by_kind"]["incident_analysis"]
    assert k["total"] == 4
    assert k["divergence_rate"] == 0.25 and k["failure_rate"] == 0.25
    assert k["cost_missing"] == 1 and k["cost_usd"] == 1.0
    assert k["by_outcome"] == {"ok": 3, "error": 1}
    assert k["feedback"] == {"useful": 1, "wrong": 1, "unread": 1, "none": 1}
    assert k["useful_rate"] == pytest.approx(1 / 3)
    assert k["avg_latency_ms"] == 200.0
    assert k["mttr_minutes"] == {"useful": None, "other": None}


async def test_metrics_empty_and_scope(api, maker):
    async with api(NOC) as c:
        assert (await c.get("/api/ai/metrics")).json()["by_kind"] == {}
    await _seed(maker, _row(1, "acme", feedback="wrong"), _row(2, "beta"))
    async with api(NOC) as c:
        k = (await c.get("/api/ai/metrics?customer_id=ACME")).json()["by_kind"]
    assert k["incident_analysis"]["total"] == 1
    assert k["incident_analysis"]["useful_rate"] == 0.0


async def test_metrics_mttr_uses_glpi_resolved_at(api, maker):
    async with maker() as s:
        s.add_all(
            [
                Incident(
                    id=i,
                    fingerprint=f"f{i}",
                    title="t",
                    host_id="h",
                    host_name="h",
                    trigger_id="t",
                    tags=tags,
                )
                for i, tags in (
                    (
                        1,
                        {"glpi_resolved_at": (NOW + timedelta(minutes=30)).isoformat()},
                    ),
                    (
                        2,
                        {"glpi_resolved_at": (NOW + timedelta(minutes=90)).isoformat()},
                    ),
                    (3, {}),
                )
            ]
        )
        await s.commit()
    await _seed(
        maker,
        _row(1, incident_id=1, feedback="useful", created_at=NOW),
        _row(2, incident_id=2, created_at=NOW),
        _row(3, incident_id=3, created_at=NOW),
        _row(4, created_at=NOW),
    )
    async with api(NOC) as c:
        k = (await c.get("/api/ai/metrics")).json()["by_kind"]["incident_analysis"]
    assert k["mttr_minutes"]["useful"] == pytest.approx(30)
    assert k["mttr_minutes"]["other"] == pytest.approx(90)


async def test_metrics_budget_reflects_platform_param(api, maker):
    async with api(NOC) as c:
        assert (await c.get("/api/ai/metrics")).json()["budget"] == {
            "month_cost_usd": 0.0,
            "limit_usd": 50.0,
        }
    await _seed(
        maker,
        _row(1, "acme", cost_usd=1.5, created_at=NOW),
        _row(2, "beta", cost_usd=2, created_at=NOW),
        _row(3, "beta", cost_usd=9, created_at=NOW.replace(day=1) - timedelta(days=1)),
    )
    async with maker() as s:
        s.add(PlatformParam(key="ai_monthly_budget_cents", value_int=1234))
        await s.commit()
    async with api(NOC) as c:
        b = (await c.get("/api/ai/metrics?customer_id=acme")).json()["budget"]
    assert b == {"month_cost_usd": 3.5, "limit_usd": 12.34}
