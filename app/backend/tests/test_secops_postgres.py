"""Triagem contra Postgres real (o CI não tem). Pulado sem NINF_TEST_PG_URL.

Ex.: NINF_TEST_PG_URL=postgresql+asyncpg://dev:dev@127.0.0.1:5439/app pytest tests/test_secops_postgres.py
"""

import asyncio
import os
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routers import secops
from app.core.dependencies import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.models import (
    AIDecision,
    Asset,
    Customer,
    CustomerAlias,
    Incident,
    PlatformParam,
    SocDecision,
    TenantMapping,
)
from app.models.users import UserRole

URL = os.environ.get("NINF_TEST_PG_URL")
pytestmark = [
    pytest.mark.skipif(not URL, reason="NINF_TEST_PG_URL não definido"),
    pytest.mark.asyncio,
]


@pytest_asyncio.fixture
async def sessions():
    engine = create_async_engine(URL)
    async with engine.begin() as c:
        tabs = [  # sem pgvector
            TenantMapping.__table__,
            SocDecision.__table__,
            Customer.__table__,
            CustomerAlias.__table__,
            PlatformParam.__table__,
            AIDecision.__table__,
            Asset.__table__,
            Incident.__table__,
        ]
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=tabs))
        # mesmo DDL de app/migrate.py
        await c.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_soc_decisions_dedup "
                "ON n_secops_soc_decisions (dedup_key) WHERE dedup_key IS NOT NULL"
            )
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def _map(maker, rows):
    async with maker() as s:
        for cust, grp in rows:
            s.add(
                TenantMapping(
                    internal_customer_id=cust,
                    external_platform="wazuh",
                    external_customer_id=grp,
                )
            )
        await s.commit()


async def test_resolve_tenant_real_db(sessions):
    await _map(
        sessions, [("cavan", "g-cavan"), ("cavan", "g-cavan-2"), ("unimed", "g-un")]
    )
    async with sessions() as s:
        r = secops._resolve_tenant
        assert await r(s, {"agent": {"group": ["g-cavan"]}}) == "cavan"
        assert await r(s, {"agent": {"groups": ["g-cavan", "g-cavan-2"]}}) == "cavan"
        assert await r(s, {"agent": {"groups": ["g-cavan", "g-un"]}}) is None  # ambíguo
        assert await r(s, {"agent": {"group": ["nao-existe"]}}) is None
        assert await r(s, {"agent": {}}) is None


async def test_concurrent_triage_dedups_once(sessions, monkeypatch):
    await _map(sessions, [("cavan", "g-cavan")])
    calls = {"llm": 0}

    async def slow_llm(payload, tenant, skip=None):
        calls["llm"] += 1
        await asyncio.sleep(0.5)  # janela para a corrida
        return {
            "classification": "HIGH",
            "confidence": 0.9,
            "summary": "x",
            "action_taken": "ESCALATE",
        }

    async def no_intel(_):
        return {"abuseipdb": None, "virustotal": None}

    monkeypatch.setattr("app.integrations.soc_agent.triage_wazuh_alert", slow_llm)
    monkeypatch.setattr("app.integrations.threat_intel.enrich_ip", no_intel)
    monkeypatch.setattr("app.integrations.threat_intel.enrich_hash", no_intel)

    async def db():
        async with sessions() as s:
            yield s

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=7, role=UserRole.soc, tenant_id=None
    )
    try:
        alert = {
            "id": "1700000000.111",
            "manager": {"name": "m1"},
            "agent": {"id": "001", "name": "pc", "group": ["g-cavan"]},
            "rule": {"id": "100100", "level": 14},
            "timestamp": "2026-11-02T10:00:00Z",
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            rs = await asyncio.gather(
                *[c.post("/api/secops/triage", json=dict(alert)) for _ in range(5)]
            )
            # alerta sem vínculo: pendente, sem tenant default, sem IA
            pend = await c.post(
                "/api/secops/triage",
                json={**alert, "id": "9.9", "agent": {"id": "002", "group": ["x"]}},
            )
    finally:
        app.dependency_overrides.clear()

    assert [r.status_code for r in rs] == [200] * 5, [r.text for r in rs]
    assert sum(1 for r in rs if r.json().get("duplicate")) == 4
    assert calls["llm"] == 1  # lock serializou: sem IA repetida
    assert pend.json()["action_taken"] == "PENDING_TENANT_REVIEW"
    async with sessions() as s:
        n = (await s.execute(select(func.count()).select_from(SocDecision))).scalar()
        cust = (await s.execute(select(SocDecision.customer_id))).scalars().all()
    assert n == 2 and sorted(map(str, cust)) == ["None", "cavan"]


async def test_archived_sample_real_db(sessions):
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)

    def row(rule, action, cust, age_days):
        return SocDecision(
            wazuh_rule_id=rule,
            customer_id=cust,
            classification="X",
            summary="s",
            action_taken=action,
            raw_alert={},
            created_at=now - timedelta(days=age_days),
        )

    async with sessions() as s:
        s.add_all(
            [
                row("a1", "ARCHIVE_NO_LLM", "cavan", 1),
                row("a2", "ARCHIVE_NO_LLM", "target", 2),
                row("old", "ARCHIVE_NO_LLM", "cavan", 20),  # fora da janela
                row("esc", "Escalated", "cavan", 1),  # não arquivado
            ]
        )
        await s.commit()

    async def db():
        async with sessions() as s:
            yield s

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=7, role=UserRole.soc, tenant_id=None
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            allr = (await c.get("/api/secops/archived-sample?days=7")).json()
            one = (await c.get("/api/secops/archived-sample?customer_id=cavan")).json()
    finally:
        app.dependency_overrides.clear()

    assert sorted(i["wazuh_rule_id"] for i in allr["items"]) == ["a1", "a2"]
    assert [i["wazuh_rule_id"] for i in one["items"]] == ["a1"]


async def test_frequency_is_persisted_and_scoped_per_tenant(sessions):
    async with sessions() as s:
        s.add(
            SocDecision(
                wazuh_rule_id="100",
                customer_id="cavan",
                classification="LOW_PRIORITY",
                confidence=0.5,
                summary="x",
                action_taken="ARCHIVE_NO_LLM",
                freq_key=secops._freq_key("cavan", {}, "001", "100"),
            )
        )
        await s.commit()
    async with sessions() as s:
        same = secops._freq_key("cavan", {}, "001", "100")
        other = secops._freq_key("unimed", {}, "001", "100")  # mesmo agente e regra
        assert (
            await secops._recent_count(s, same) == 1
        )  # sobrevive a novo processo/sessão
        assert await secops._recent_count(s, other) == 0  # não soma entre tenants


async def test_frequency_window_excludes_old_rows(sessions):
    from datetime import UTC, datetime, timedelta

    key = secops._freq_key("cavan", {}, "001", "7")
    async with sessions() as s:
        for age in (10, 3600):  # segundos: dentro e fora da janela de 5 min
            s.add(
                SocDecision(
                    wazuh_rule_id="7",
                    classification="LOW_PRIORITY",
                    confidence=0.5,
                    summary="x",
                    action_taken="ARCHIVE_NO_LLM",
                    freq_key=key,
                    created_at=datetime.now(UTC) - timedelta(seconds=age),
                )
            )
        await s.commit()
    async with sessions() as s:
        assert await secops._recent_count(s, key) == 1
        assert await secops._recent_count(s, None) == 0


async def test_burst_with_same_freq_key_counts_in_series(sessions, monkeypatch):
    await _map(sessions, [("cavan", "g-cavan")])
    seen = []
    real = secops._recent_count

    async def spy(db, key):
        n = await real(db, key)
        seen.append(n)
        await asyncio.sleep(0.2)  # abre a corrida entre a contagem e o commit
        return n

    async def no_intel(_):
        return {"abuseipdb": None, "virustotal": None}

    monkeypatch.setattr(secops, "_recent_count", spy)
    monkeypatch.setattr("app.integrations.threat_intel.enrich_ip", no_intel)
    monkeypatch.setattr("app.integrations.threat_intel.enrich_hash", no_intel)

    async def db():
        async with sessions() as s:
            yield s

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=7, role=UserRole.soc, tenant_id=None
    )
    try:
        base = {
            "manager": {"name": "m1"},
            "agent": {"id": "001", "name": "pc", "group": ["g-cavan"]},
            "rule": {"id": "555", "level": 3},
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            rs = await asyncio.gather(
                *[
                    c.post("/api/secops/triage", json={**base, "id": f"1.{i}"})
                    for i in range(4)
                ]
            )
    finally:
        app.dependency_overrides.clear()
    assert [r.status_code for r in rs] == [200] * 4, [r.text for r in rs]
    assert sorted(seen) == [0, 1, 2, 3]  # cada alerta enxerga os anteriores


async def _triage_via_api(sessions, monkeypatch, alerts, model_class="FP"):
    """Triagem de ponta a ponta com o modelo simulado no transporte HTTP do soc_agent."""
    import json

    from app.integrations import soc_agent

    monkeypatch.setattr(soc_agent.settings, "llm_api_key", "k")
    http = {"n": 0}

    async def model(*a, **k):
        http["n"] += 1
        reply = {
            "classification": model_class,
            "confidence": 0.9,
            "summary": "s",
            "action_taken": "a",
        }
        return json.dumps(reply), {"model": "m1", "cost": 0.002}

    async def no_intel(_):
        return {"abuseipdb": None, "virustotal": None}

    monkeypatch.setattr(soc_agent, "achat_completion", model)
    monkeypatch.setattr("app.integrations.threat_intel.enrich_ip", no_intel)
    monkeypatch.setattr("app.integrations.threat_intel.enrich_hash", no_intel)

    async def db():
        async with sessions() as s:
            yield s

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=7, role=UserRole.soc, tenant_id=None
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            return http, [
                (await c.post("/api/secops/triage", json=a)).json() for a in alerts
            ]
    finally:
        app.dependency_overrides.clear()


async def test_triage_records_ai_decision_linked_to_soc_decision(sessions, monkeypatch):
    await _map(sessions, [("cavan", "g-cavan")])
    alert = {
        "id": "1700000000.111",
        "manager": {"name": "m1"},
        "agent": {"id": "001", "name": "pc", "group": ["g-cavan"]},
        "rule": {"id": "100100", "level": 14},
        "timestamp": "2026-11-02T10:00:00Z",
    }
    monkeypatch.setattr(
        secops._triage_engine,
        "evaluate_alert",
        lambda **kw: SimpleNamespace(
            action=secops.TriageAction.TRIAGE_L2, risk_score=90
        ),
    )
    http, (out,) = await _triage_via_api(sessions, monkeypatch, [alert])

    assert out["attendance_required"] is True and http["n"] == 1
    assert not any(k.startswith("_ai") for k in out)
    async with sessions() as s:
        dec = (await s.execute(select(SocDecision))).scalar_one()
        row = (await s.execute(select(AIDecision))).scalar_one()
    assert out["decision_id"] == dec.id and row.soc_decision_id == dec.id
    assert row.kind == "soc_triage" and row.customer_id == "cavan"
    assert row.source_ref == dec.dedup_key and row.prompt_version == "soc-2026-11-17"
    assert row.outcome == "ok" and row.model == "m1"
    assert row.model_value == "FP" and row.rule_value == "TRIAGE_L2"
    assert row.divergent is True  # motor L2, modelo FP
    assert row.response["classification"] == "FP"
    assert not any(k.startswith("_ai") for k in dec.raw_alert)


async def test_archived_and_pending_do_not_record(sessions, monkeypatch):
    await _map(sessions, [("cavan", "g-cavan")])
    archived = {
        "id": "1.1",
        "agent": {"id": "001", "name": "pc", "group": ["g-cavan"]},
        "rule": {"id": "100200", "level": 3},
    }
    pending = {
        "id": "2.2",
        "agent": {"id": "002", "name": "pc", "group": ["sem-vinculo"]},
        "rule": {"id": "100200", "level": 14},
    }
    http, outs = await _triage_via_api(sessions, monkeypatch, [archived, pending])

    assert [o["action_taken"] for o in outs] == [
        "ARCHIVE_NO_LLM",
        "PENDING_TENANT_REVIEW",
    ]
    assert http["n"] == 0
    async with sessions() as s:
        assert (
            await s.execute(select(func.count()).select_from(AIDecision))
        ).scalar() == 0


async def test_disabled_customer_records_skip_without_divergence(sessions, monkeypatch):
    await _map(sessions, [("cavan", "g-cavan")])
    async with sessions() as s:
        s.add(Customer(key="cavan", display_name="Cavan", ai_external_allowed=False))
        await s.commit()
    alert = {
        "id": "3.3",
        "agent": {"id": "001", "name": "pc", "group": ["g-cavan"]},
        "rule": {"id": "100100", "level": 14},
    }
    http, (out,) = await _triage_via_api(sessions, monkeypatch, [alert])

    assert http["n"] == 0 and out["attendance_required"] is True
    async with sessions() as s:
        row = (await s.execute(select(AIDecision))).scalar_one()
    assert row.outcome == "skipped_customer" and row.model_value is None
    assert row.divergent is False


async def _wazuh_level(sessions, monkeypatch, level):
    async with sessions() as s:
        s.add(
            Customer(key="cavan", display_name="Cavan", glpi_entity_id=8, active=True)
        )
        await s.commit()
    await _map(sessions, [("cavan", "g-cavan")])
    alert = {
        "id": "1700000000.222",
        "manager": {"name": "m1"},
        "agent": {"id": "001", "name": "pc", "group": ["g-cavan"]},
        "rule": {"id": "100100", "level": level, "description": "RDP"},
        "timestamp": "2026-11-02T10:00:00Z",
    }
    await _triage_via_api(sessions, monkeypatch, [alert])
    async with sessions() as s:
        return (await s.execute(select(Incident))).scalars().all()


async def test_wazuh_level12_creates_pending_soc_incident(sessions, monkeypatch):
    (inc,) = await _wazuh_level(sessions, monkeypatch, 12)
    assert inc.tags["ninf_ticket_state"] == "pending"
    assert inc.tags["ninf_branch"] == "soc" and inc.tags["ninf_entity_id"] == 8
    assert (
        inc.tags["ninf_customer_name"] == "cavan"
    )  # chave: é o que a autorização compara
    async with sessions() as s:
        assert (await s.execute(select(SocDecision.incident_id))).scalar_one() == inc.id


async def test_wazuh_level10_creates_no_incident(sessions, monkeypatch):
    assert await _wazuh_level(sessions, monkeypatch, 10) == []


async def test_wazuh_ticket_level_is_configurable(sessions, monkeypatch):
    async with sessions() as s:
        s.add(PlatformParam(key="soc_ticket_min_level", value_int=13))
        await s.commit()
    assert await _wazuh_level(sessions, monkeypatch, 12) == []
