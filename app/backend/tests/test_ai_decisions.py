"""record_ai_decision e o worker NOC contra Postgres real. Pulado sem NINF_TEST_PG_URL."""

import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
    TicketLink,
)
from app.services.ai_decisions import record_ai_decision
from app.workers import alerts, ticket_decider

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
    TicketLink.__table__,
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


async def _record(session, call=CALL, **kw):
    return await record_ai_decision(
        session,
        kind="incident_analysis",
        customer_id="acme",
        source_ref="fp:1",
        call=call,
        prompt_version="v",
        request={},
        response={},
        rule_value="MEDIUM",
        model_value="CRITICAL",
        **kw,
    )


async def test_record_marks_divergence_and_is_idempotent(maker):
    async with maker() as s, s.begin():
        first = await _record(s, incident_id=5)
        assert await _record(s) is None
    assert first is not None
    async with maker() as s:
        rows = (await s.execute(select(AIDecision))).scalars().all()
    assert len(rows) == 1
    assert rows[0].divergent is True
    assert rows[0].cost_usd is None  # absurd cost never breaks NUMERIC(10,6)

    retry = AICall("incident_analysis", "ok", "m", 12, 10, 5, 0.01)
    async with maker() as s, s.begin():
        assert await _record(s, call=retry, ticket_id="77") is None
        assert await _record(s, call=retry, incident_id=9) is None
    async with maker() as s:
        rows = (await s.execute(select(AIDecision))).scalars().all()
    assert len(rows) == 1
    assert rows[0].cost_usd == Decimal("0.02")
    assert (rows[0].prompt_tokens, rows[0].completion_tokens) == (40, 20)
    assert (rows[0].ticket_id, rows[0].incident_id) == ("77", 5)


async def test_record_failure_does_not_abort_transaction(maker):
    async with maker() as s, s.begin():
        assert await _record(s, ticket_id="x" * 100) is None  # too long for column
        s.add(Customer(key="acme", display_name="Acme"))
    async with maker() as s:
        assert await s.scalar(select(func.count(Customer.id))) == 1


NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


async def _pending(maker, fp, sev, event):
    """Incidente já gravado pela ingestão, vencido a carência, aguardando o decisor."""
    async with maker() as s:
        s.add(
            Incident(
                fingerprint=fp,
                title="Linux: FS [/]: Space is critically low",
                severity=sev,
                status="open",
                host_id="h",
                host_name="h",
                trigger_id="t",
                first_seen=NOW - timedelta(minutes=30),
                last_seen=NOW,
                tags={
                    "ninf_customer_name": "Acme",
                    "ninf_entity_id": 8,
                    "ninf_dedup_key": f"8:h:{fp[:8]}",
                    "ninf_zabbix_event_id": event,
                    "ninf_ticket_state": "pending",
                },
            )
        )
        await s.commit()


def _decider(monkeypatch, maker):
    monkeypatch.setattr(alerts, "SessionLocal", maker)
    monkeypatch.setattr(ticket_decider, "SessionLocal", maker)
    monkeypatch.setattr(
        alerts, "ensure_glpi_ticket_serialized", AsyncMock(return_value=(77, True))
    )
    monkeypatch.setattr(alerts, "lookup_glpi_asset", AsyncMock(return_value=None))
    return AsyncMock()


async def test_decider_records_decision_with_incident_and_ticket(maker, monkeypatch):
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
    monkeypatch.setattr(ticket_decider.settings, "llm_api_key", "synthetic-key")
    glpi = _decider(monkeypatch, maker)
    await _pending(maker, "f" * 64, 3, "42")
    async with maker() as s:
        inc = (await s.execute(select(Incident))).scalar_one()

    assert await ticket_decider._open(glpi, inc, NOW, 24) == "opened"

    async with maker() as s:
        row = (await s.execute(select(AIDecision))).scalar_one()
    assert row.kind == "incident_analysis"
    assert row.incident_id == inc.id
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


async def test_decider_gate_error_records_no_model_opinion(maker, monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("No provider call when the gate fails")

    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    monkeypatch.setattr(llm.settings, "llm_api_key", "synthetic-key")
    monkeypatch.setattr(ticket_decider.settings, "llm_api_key", "synthetic-key")
    monkeypatch.setattr(alerts, "ai_gate", AsyncMock(side_effect=RuntimeError))
    glpi = _decider(monkeypatch, maker)
    await _pending(maker, "g" * 64, 5, "7")
    async with maker() as s:
        inc = (await s.execute(select(Incident))).scalar_one()

    await ticket_decider._open(glpi, inc, NOW, 24)

    async with maker() as s:
        row = (await s.execute(select(AIDecision))).scalar_one()
    assert (row.outcome, row.rule_value, row.model_value) == ("error", "CRITICAL", None)
    assert row.divergent is False and row.response == {}


async def test_decider_without_key_skips_gate(maker, monkeypatch):
    gate = AsyncMock()
    monkeypatch.setattr(ticket_decider.settings, "llm_api_key", "")
    monkeypatch.setattr(alerts, "ai_gate", gate)
    analyze = AsyncMock(side_effect=StopAsyncIteration)  # stop right after analysis
    monkeypatch.setattr(ticket_decider, "analyze_incident", analyze)
    glpi = _decider(monkeypatch, maker)
    await _pending(maker, "h" * 64, 4, "1")
    async with maker() as s:
        inc = (await s.execute(select(Incident))).scalar_one()
    with pytest.raises(StopAsyncIteration):
        await ticket_decider._open(glpi, inc, NOW, 24)
    gate.assert_not_awaited()
    assert analyze.await_args.kwargs["skip"] is None


async def test_ingestion_never_calls_the_model(maker, monkeypatch):
    """Com a regra de chamados a IA só roda quando o decisor abre chamado."""
    analyze = AsyncMock()
    monkeypatch.setattr(ticket_decider, "analyze_incident", analyze)
    monkeypatch.setattr(alerts, "SessionLocal", maker)
    monkeypatch.setattr(
        alerts, "resolve_alert_customer", AsyncMock(return_value=("Acme", None))
    )
    monkeypatch.setattr(
        alerts, "canonical_customer", AsyncMock(return_value=("Acme", 8))
    )
    monkeypatch.setattr(alerts, "_get_sync_redis", lambda: MagicMock())
    monkeypatch.setattr(alerts, "LokiClient", lambda: AsyncMock())
    alert = {"host_name": "h", "trigger_name": "t", "severity": 3, "event_id": "42"}
    await alerts._async_process_alert_v1(alert, "i" * 64)
    analyze.assert_not_awaited()
    async with maker() as s:
        assert (await s.scalar(select(func.count(AIDecision.id)))) == 0
