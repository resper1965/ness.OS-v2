"""ai_gate contra Postgres real. Pulado sem NINF_TEST_PG_URL.

Ex.: NINF_TEST_PG_URL=postgresql+asyncpg://dev:dev@127.0.0.1:5439/app pytest tests/test_ai_gate.py
"""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import Base
from app.models.models import AIDecision, Customer, CustomerAlias, PlatformParam
from app.services import ai_gate as gate

URL = os.environ.get("NINF_TEST_PG_URL")
pytestmark = [
    pytest.mark.skipif(not URL, reason="NINF_TEST_PG_URL não definido"),
    pytest.mark.asyncio,
]

TABLES = [
    Customer.__table__,
    CustomerAlias.__table__,
    PlatformParam.__table__,
    AIDecision.__table__,
]


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(URL)
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=TABLES))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=TABLES))
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def emails(monkeypatch):
    sent = []

    class Fake:
        async def send(self, **kw):
            sent.append(kw)

    monkeypatch.setattr(
        gate.ResendEmailClient, "from_settings", classmethod(lambda cls, s=None: Fake())
    )
    monkeypatch.setattr(get_settings(), "ai_budget_alert_email", "ops@example.com")
    monkeypatch.setattr(get_settings(), "transactional_email_enabled", True)
    return sent


def _row(ref, outcome="ok", cost=None, created_at=None):
    return AIDecision(
        kind="noc_incident",
        customer_id="acme",
        source_ref=ref,
        outcome=outcome,
        prompt_version="v1",
        cost_usd=None if cost is None else Decimal(cost),
        **({"created_at": created_at} if created_at else {}),
    )


async def test_gate_open_by_default(session, emails):
    session.add(Customer(key="acme", display_name="Acme S.A."))
    await session.commit()
    assert await gate.ai_gate(session, "Acme S.A.") is None
    assert await gate.ai_gate(session, "desconhecido") is None
    assert emails == []


async def test_gate_customer_disabled(session, emails):
    session.add(Customer(key="acme", display_name="Acme", ai_external_allowed=False))
    await session.commit()
    assert await gate.ai_gate(session, "ACME") == "skipped_customer"


async def test_gate_budget_reached_sends_one_email(session, emails):
    session.add(_row("a", cost="50.00"))
    await session.commit()
    assert await gate.ai_gate(session, "acme") == "skipped_budget"
    assert len(emails) == 1
    assert emails[0]["to"] == ["ops@example.com"]
    assert (
        emails[0]["idempotency_key"] == f"ai-budget-{datetime.now(timezone.utc):%Y-%m}"
    )
    session.add(_row("b", outcome="skipped_budget"))
    await session.commit()
    assert await gate.ai_gate(session, "acme") == "skipped_budget"
    assert len(emails) == 1


async def test_gate_ignores_previous_month_and_null_cost(session, emails):
    old = datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)
    session.add_all([_row("old", cost="60.00", created_at=old), _row("null")])
    await session.commit()
    assert await gate.ai_gate(session, "acme") is None


async def test_gate_email_failure_never_raises(session, emails, monkeypatch):
    class Boom:
        async def send(self, **kw):
            raise RuntimeError("resend down")

    monkeypatch.setattr(
        gate.ResendEmailClient, "from_settings", classmethod(lambda cls, s=None: Boom())
    )
    session.add(_row("a", cost="50.00"))
    await session.commit()
    assert await gate.ai_gate(session, "acme") == "skipped_budget"
