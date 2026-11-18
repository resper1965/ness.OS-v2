"""record_ai_decision e o worker NOC contra Postgres real. Pulado sem NINF_TEST_PG_URL."""

import json
import os
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.ai_context import AICall
from app.database import Base
from app.integrations import llm
from app.ml.analyzer import PROMPT_VERSION_NOC
from app.models.models import (
    AIDecision,
    Asset,
    Customer,
    CustomerAlias,
    Incident,
    IncidentAction,
    PlatformParam,
)
from app.services.ai_decisions import record_ai_decision
from app.workers import alerts

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
    IncidentAction.__table__,
    AIDecision.__table__,
]


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


CALL = AICall("incident_analysis", "ok", "m", 12, 10, 5, 1e9)


async def _record(session, **kw):
    return await record_ai_decision(
        session,
        kind="incident_analysis",
        customer_id="acme",
        source_ref="fp:1",
        call=CALL,
        prompt_version="v",
        request={},
        response={},
        rule_value="MEDIUM",
        model_value="CRITICAL",
        **kw,
    )


async def test_record_marks_divergence_and_is_idempotent(maker):
    async with maker() as s, s.begin():
        first = await _record(s)
        assert await _record(s) is None
    assert first is not None
    async with maker() as s:
        rows = (await s.execute(select(AIDecision))).scalars().all()
    assert len(rows) == 1
    assert rows[0].divergent is True
    assert rows[0].cost_usd is None  # absurd cost never breaks NUMERIC(10,6)


async def test_record_failure_does_not_abort_transaction(maker):
    async with maker() as s, s.begin():
        assert await _record(s, ticket_id="x" * 100) is None  # too long for column
        s.add(Customer(key="acme", display_name="Acme"))
    async with maker() as s:
        assert await s.scalar(select(func.count(Customer.id))) == 1


async def test_worker_records_decision_with_incident_and_ticket(maker, monkeypatch):
    payload = {
        "executive_action_plan": "x",
        "technical_action_plan": "x",
        "urgency": "CRITICAL",
        "isolation_required": False,
        "probable_cause": "x",
        "recommended_playbook": "x",
    }
    original = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(payload)}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "cost": 0.01},
            },
        )
    )
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: original(transport=transport, **kw)
    )
    monkeypatch.setattr(llm.settings, "llm_api_key", "synthetic-key")
    monkeypatch.setattr(alerts, "SessionLocal", maker)
    monkeypatch.setattr(alerts, "GLPIClient", lambda: AsyncMock())
    monkeypatch.setattr(
        alerts, "ensure_glpi_ticket_serialized", AsyncMock(return_value=(77, True))
    )
    monkeypatch.setattr(
        alerts, "resolve_alert_customer", AsyncMock(return_value="Acme")
    )
    monkeypatch.setattr(
        alerts, "canonical_customer", AsyncMock(return_value=("Acme", 8))
    )
    monkeypatch.setattr(alerts, "lookup_glpi_asset", AsyncMock(return_value=None))
    monkeypatch.setattr(alerts, "_get_sync_redis", lambda: MagicMock())
    monkeypatch.setattr(alerts, "LokiClient", lambda: AsyncMock())

    alert = {"host_name": "h", "trigger_name": "t", "severity": 3, "event_id": "42"}
    result = await alerts._async_process_alert_v1(alert, "f" * 64)

    async with maker() as s:
        rows = (await s.execute(select(AIDecision))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "incident_analysis"
    assert row.incident_id == result["id"]
    assert row.ticket_id == "77"
    assert row.source_ref == f"{'f' * 64}:42"
    assert row.prompt_version == PROMPT_VERSION_NOC
    assert (row.outcome, row.rule_value, row.model_value) == (
        "ok",
        "MEDIUM",
        "CRITICAL",
    )
    assert row.divergent is True
    assert row.request["tenant"] == "Acme"
    assert "customer_metadata" not in row.request and "entity_id" not in str(
        row.request
    )
    assert row.response["urgency"] == "CRITICAL"
