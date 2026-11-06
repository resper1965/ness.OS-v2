"""Parâmetros da política de atendimento por contrato e globais da plataforma.

Parte pura roda sempre; o resto exige NINF_TEST_PG_URL (Postgres real, como test_sla_contracts).
"""

import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routers import contracts as contracts_router
from app.api.routers import secops
from app.config import get_settings
from app.core.dependencies import get_current_user
from app.core.triage_engine import TriageAction, TriageEngine
from app.database import Base, get_db
from app.integrations import pipeline_health as health
from app.migrate import apply_params_sql, apply_sla_sql
from app.models import (
    Contract,
    ContractChange,
    ContractPolicyParam,
    EscalationStep,
    PlatformParam,
    SlaCalendar,
    SlaCalendarHours,
    SlaHoliday,
    SlaPolicy,
    SocDecision,
    UserRole,
)
from app.services.policy_params import (
    CONTRACT_DEFAULTS,
    PLATFORM_DEFAULTS,
    clamp,
    get_param,
    get_params,
    platform_params,
)

URL = os.environ.get("NINF_TEST_PG_URL")
pg = pytest.mark.skipif(not URL, reason="NINF_TEST_PG_URL não definido")
ROOT = Path(__file__).parents[1]
TABLES = (
    SocDecision, SlaCalendar, SlaCalendarHours, SlaHoliday, Contract, SlaPolicy,
    EscalationStep, ContractChange, ContractPolicyParam, PlatformParam,
)  # fmt: skip
BASE = "/api/v1/sla"

# ---------- puro ----------


def test_defaults_equal_legacy_constants():
    """Os padrões repetem o que estava em código antes desta mudança."""
    assert (
        CONTRACT_DEFAULTS["soc_attend_min_level"] == 12
    )  # config.soc_attendance_min_level
    assert CONTRACT_DEFAULTS["soc_archive_score_floor"] == 75
    assert TriageEngine().threshold_l1 == 75  # constante do motor, hoje fallback
    assert CONTRACT_DEFAULTS["ot_retrospective_hours"] == 24
    assert CONTRACT_DEFAULTS["weekly_sample_per_client"] == 20
    assert CONTRACT_DEFAULTS["weekly_sample_pct"] == 10
    assert CONTRACT_DEFAULTS["weekly_sample_threshold"] == 200
    assert PLATFORM_DEFAULTS == {
        "source_max_age_seconds": 900,
        "queue_max_age_seconds": 300,
        "worker_failure_window_seconds": 900,
        "probe_timeout_seconds": 20,
    }
    assert (health.MAX_SOURCE_AGE_SECONDS, health.MAX_QUEUE_AGE_SECONDS) == (900, 300)
    assert (health.WORKER_FAILURE_WINDOW_SECONDS, health.PROBE_TIMEOUT_SECONDS) == (
        900,
        20,
    )
    assert not hasattr(get_settings(), "soc_attendance_min_level")  # sem segunda fonte


def test_seed_in_migrate_equals_defaults():
    """O seed do banco (única cópia editável) também é igual às constantes antigas."""
    sql = (ROOT / "app" / "migrate.py").read_text()
    seeded = dict(
        (k, int(v))
        for k, v in re.findall(r"\('([a-z_]+)', (\d+)\)", sql.split("PARAMS_SQL")[1])
    )
    assert seeded == {**CONTRACT_DEFAULTS, **PLATFORM_DEFAULTS}


def test_floor_clamps_to_12():
    assert clamp("soc_attend_min_level", 15) == 12  # valor legado inválido não afrouxa
    assert clamp("soc_attend_min_level", 9) == 9
    assert clamp("weekly_sample_per_client", 5) == 20


@pytest.mark.parametrize(
    ("archived", "expected"), [(0, 20), (150, 20), (200, 20), (201, 21), (1000, 100)]
)
def test_sample_quota(archived, expected):
    assert secops.sample_quota(archived, 20, 10, 200) == expected


def test_attendance_uses_effective_floor_param():
    low = {"level": 10, "level_invalid": False}
    assert secops._attendance_required(False, TriageAction.ARCHIVE, low, 12) is False
    assert secops._attendance_required(False, TriageAction.ARCHIVE, low, 10) is True


def test_score_floor_param_changes_archive_decision():
    alert = {"level": 14, "host": "prod-dc-01"}  # 81 pts
    e = TriageEngine()
    assert e.evaluate_alert(alert).action != TriageAction.ARCHIVE
    assert e.evaluate_alert(alert, threshold_l1=90).action == TriageAction.ARCHIVE


# ---------- Postgres ----------


@pytest_asyncio.fixture
async def maker():
    engine = create_async_engine(URL)
    tabs = [t.__table__ for t in TABLES]
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=tabs))
        await apply_sla_sql(c)
        await apply_params_sql(c)
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
    await engine.dispose()


async def _contract(maker, tenant="acme", status="active", **kw):
    async with maker() as s:
        cal = await s.scalar(select(SlaCalendar.id).where(SlaCalendar.name == "24x7"))
        c = Contract(tenant_id=tenant, name="c", status=status, calendar_id=cal, **kw)
        s.add(c)
        await s.commit()
        return c.id


async def _set(maker, cid, key, value):
    async with maker() as s:
        await s.merge(ContractPolicyParam(contract_id=cid, key=key, value_int=value))
        await s.commit()


def _api(maker, role, tenant=None):
    app = FastAPI()
    app.include_router(contracts_router.router)
    user = SimpleNamespace(id=7, role=role, tenant_id=tenant, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user

    async def db():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_db] = db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@pg
@pytest.mark.asyncio
async def test_contract_overrides_default(maker):
    cid = await _contract(maker)
    await _set(maker, cid, "soc_attend_min_level", 9)
    async with maker() as s:
        v = await get_param(s, "ACME", "soc_attend_min_level")  # tenant sem caixa
        assert (v.value, v.contractual) == (9, True)
        other = await get_param(s, "outro", "soc_attend_min_level")
        assert (other.value, other.contractual) == (12, False)  # padrão, não contratual
        none = await get_param(s, None, "ot_retrospective_hours")
        assert (none.value, none.contractual) == (24, False)


@pg
@pytest.mark.asyncio
async def test_non_contractual_flag_present(maker):
    cid = await _contract(maker)
    await _set(maker, cid, "weekly_sample_per_client", 30)
    async with maker() as s:
        p = await get_params(s, "acme")
        assert p["weekly_sample_per_client"].contractual is True
        assert p["soc_archive_score_floor"].contractual is False  # herdado do padrão
    async with _api(maker, UserRole.noc) as c:
        default_id = (await c.get(f"{BASE}/contracts")).json()[0]["id"]
        body = (await c.get(f"{BASE}/contracts/{default_id}/params")).json()
        assert body["contractual"] is False
        assert body["params"]["soc_attend_min_level"]["effective"] == 12


@pg
@pytest.mark.asyncio
async def test_param_edit_effective_next_call(maker):
    cid = await _contract(maker)
    async with maker() as s:
        assert (await get_param(s, "acme", "soc_archive_score_floor")).value == 75
    async with _api(maker, UserRole.admin) as c:
        r = await c.put(
            f"{BASE}/contracts/{cid}/params/soc_archive_score_floor", json={"value": 60}
        )
        assert r.status_code == 200
    async with maker() as s:  # sem reiniciar nada
        assert (await get_param(s, "acme", "soc_archive_score_floor")).value == 60
        changes = (await s.execute(select(ContractChange))).scalars().all()
    assert [(c.entity, c.after) for c in changes] == [
        ("policy_param", {"key": "soc_archive_score_floor", "value": 60})
    ]


@pg
@pytest.mark.asyncio
async def test_ended_or_expired_contract_param_ignored(maker):
    cid = await _contract(maker, "acme")
    await _set(maker, cid, "soc_attend_min_level", 5)
    async with maker() as s:
        assert (await get_param(s, "acme", "soc_attend_min_level")).value == 5
        await s.execute(
            text(
                "UPDATE n_infraops_contracts SET ends_on = '2020-01-01' WHERE id = :i"
            ),
            {"i": cid},
        )
        await s.commit()
        assert (await get_param(s, "acme", "soc_attend_min_level")).value == 12


@pg
@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["ot_retrospective_hours", "soc_attend_min_level"])
async def test_ot_hours_over_24_rejected_422(maker, key):
    cid = await _contract(maker)
    limit = {"ot_retrospective_hours": 24, "soc_attend_min_level": 12}[key]
    async with _api(maker, UserRole.admin) as c:
        url = f"{BASE}/contracts/{cid}/params/{key}"
        assert (await c.put(url, json={"value": limit + 1})).status_code == 422
        assert (await c.put(url, json={"value": 0})).status_code == 422
        assert (await c.put(url, json={"value": limit})).status_code == 200
    async with maker() as s:
        assert (await get_param(s, "acme", key)).value == limit


@pg
@pytest.mark.asyncio
async def test_floor_above_12_rejected_422(maker):
    cid = await _contract(maker)
    async with _api(maker, UserRole.admin) as c:
        r = await c.put(
            f"{BASE}/contracts/{cid}/params/soc_attend_min_level", json={"value": 13}
        )
        assert r.status_code == 422
    async with maker() as s:  # nada gravado
        assert (
            await s.scalar(
                select(ContractPolicyParam).where(
                    ContractPolicyParam.contract_id == cid
                )
            )
            is None
        )
    # o banco também recusa (defesa em profundidade)
    async with maker() as s:
        with pytest.raises(Exception, match="ck_policy_params_ceiling"):
            await s.execute(
                text(
                    "INSERT INTO n_infraops_contract_policy_params (contract_id, key, value_int) VALUES (:c, 'soc_attend_min_level', 13)"
                ),
                {"c": cid},
            )


@pg
@pytest.mark.asyncio
async def test_floor_below_12_accepted_effective_min(maker):
    cid = await _contract(maker)
    async with _api(maker, UserRole.admin) as c:
        r = await c.put(
            f"{BASE}/contracts/{cid}/params/soc_attend_min_level", json={"value": 8}
        )
        assert r.status_code == 200
    async with maker() as s:
        assert (await get_param(s, "acme", "soc_attend_min_level")).value == min(8, 12)


@pg
@pytest.mark.asyncio
async def test_params_authz_and_unknown_key(maker):
    cid = await _contract(maker)
    for role in (UserRole.operator, UserRole.noc, UserRole.viewer, UserRole.cliente):
        async with _api(maker, role, "acme") as c:
            r = await c.put(
                f"{BASE}/contracts/{cid}/params/soc_attend_min_level", json={"value": 8}
            )
            assert r.status_code == 403
    async with _api(maker, UserRole.admin) as c:
        assert (
            await c.put(f"{BASE}/contracts/{cid}/params/x", json={"value": 8})
        ).status_code == 404
    # operator só lê o próprio contrato (lição do #198)
    other = await _contract(maker, "beta")
    async with _api(maker, UserRole.operator, "acme") as c:
        assert (await c.get(f"{BASE}/contracts/{cid}/params")).status_code == 200
        assert (await c.get(f"{BASE}/contracts/{other}/params")).status_code == 404
    async with _api(maker, UserRole.viewer, "acme") as c:
        assert (await c.get(f"{BASE}/contracts/{cid}/params")).status_code == 403


@pg
@pytest.mark.asyncio
async def test_platform_params_only_platform_admin_edits(maker):
    for role in (UserRole.admin, UserRole.noc, UserRole.operator):
        async with _api(maker, role) as c:
            r = await c.put(
                f"{BASE}/platform-params/source_max_age_seconds", json={"value": 600}
            )
            assert r.status_code == 403
    async with _api(maker, UserRole.platform_admin) as c:
        assert (
            await c.put(
                f"{BASE}/platform-params/source_max_age_seconds", json={"value": 600}
            )
        ).status_code == 200
        assert (
            await c.put(
                f"{BASE}/platform-params/probe_timeout_seconds", json={"value": 40}
            )
        ).status_code == 422
        assert (
            await c.put(f"{BASE}/platform-params/nope", json={"value": 1})
        ).status_code == 404
    async with _api(maker, UserRole.noc) as c:
        assert (await c.get(f"{BASE}/platform-params")).json()[
            "source_max_age_seconds"
        ]["value"] == 600
    async with _api(maker, UserRole.operator) as c:
        assert (await c.get(f"{BASE}/platform-params")).status_code == 403
    async with maker() as s:
        assert (await platform_params(s))["source_max_age_seconds"] == 600


@pg
@pytest.mark.asyncio
async def test_platform_param_edit_changes_freshness_next_cycle(maker, monkeypatch):
    monkeypatch.setattr(health, "SessionLocal", maker)
    assert (await health.load_params())["source_max_age_seconds"] == 900
    async with maker() as s:
        await s.merge(PlatformParam(key="source_max_age_seconds", value_int=60))
        await s.commit()
    assert (await health.load_params())["source_max_age_seconds"] == 60
    now = datetime.now(UTC)
    old = now - timedelta(seconds=120)
    out = await health.with_freshness(
        "x", {"status": "ok"}, SimpleNamespace(set=_noop, get=_noop), old, 60
    )
    assert out["stale"] is False
    out = await health.with_freshness(
        "x",
        {"status": "ok"},
        SimpleNamespace(set=_noop, get=_noop),
        now - timedelta(seconds=0),
        60,
    )
    assert out["stale"] is False


async def _noop(*a):
    return None


@pg
@pytest.mark.asyncio
async def test_platform_params_unavailable_falls_back_to_defaults(monkeypatch):
    def boom():
        raise ConnectionError("db")

    monkeypatch.setattr(health, "SessionLocal", boom)
    assert await health.load_params() == PLATFORM_DEFAULTS


# ---------- amostra semanal ----------


async def _archive(maker, customer, n, age_days=1):
    async with maker() as s:
        s.add_all(
            SocDecision(
                wazuh_rule_id=f"r{i}", customer_id=customer, classification="X",
                summary="s", action_taken="ARCHIVE_NO_LLM", raw_alert={},
                created_at=datetime.now(UTC) - timedelta(days=age_days),
            )
            for i in range(n)
        )  # fmt: skip
        await s.commit()


def _sample_client(maker, role=UserRole.soc, tenant=None):
    app = FastAPI()
    app.include_router(secops.router)
    user = SimpleNamespace(id=7, role=role, tenant_id=tenant, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user

    async def db():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_db] = db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


def _by_customer(items):
    out = {}
    for i in items:
        out[i["customer_id"]] = out.get(i["customer_id"], 0) + 1
    return out


@pg
@pytest.mark.asyncio
async def test_sample_20_per_client(maker):
    await _archive(maker, "cavan", 50)
    await _archive(maker, "target", 30)
    await _archive(maker, "unimed", 5)
    await _archive(maker, "cavan", 99, age_days=20)  # fora da janela
    async with _sample_client(maker) as c:
        body = (await c.get("/api/secops/archived-sample?days=7")).json()
    assert _by_customer(body["items"]) == {"cavan": 20, "target": 20, "unimed": 5}
    assert body["groups"]["cavan"] == {
        "archived": 50,
        "quota": 20,
        "sampled": 20,
        "contractual": False,
    }


@pg
@pytest.mark.asyncio
async def test_sample_10pct_above_200(maker):
    await _archive(maker, "cavan", 300)
    await _archive(maker, "target", 200)  # exatamente 200: ainda 20
    async with _sample_client(maker) as c:
        body = (await c.get("/api/secops/archived-sample")).json()
    assert _by_customer(body["items"]) == {"cavan": 30, "target": 20}
    # limit vira teto por cliente, não regra
    async with _sample_client(maker) as c:
        body = (await c.get("/api/secops/archived-sample?limit=5")).json()
    assert _by_customer(body["items"]) == {"cavan": 5, "target": 5}


@pg
@pytest.mark.asyncio
async def test_sample_param_edit_effective(maker):
    cid = await _contract(maker, "cavan")
    await _archive(maker, "cavan", 100)
    await _archive(maker, "target", 100)
    async with _sample_client(maker) as c:
        assert _by_customer(
            (await c.get("/api/secops/archived-sample")).json()["items"]
        ) == {"cavan": 20, "target": 20}
        await _set(maker, cid, "weekly_sample_per_client", 40)
        body = (await c.get("/api/secops/archived-sample")).json()
    assert _by_customer(body["items"]) == {"cavan": 40, "target": 20}
    assert (
        body["groups"]["cavan"]["contractual"] is False
    )  # só uma das chaves é do contrato
    # operator/tenant não lê amostra (evidência bruta é NOC)
    async with _sample_client(maker, UserRole.operator, "cavan") as c:
        assert (await c.get("/api/secops/archived-sample")).status_code == 403
