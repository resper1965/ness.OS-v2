"""P3: dois canais, ack e escalonamento. Parte pura roda sempre; o resto exige NINF_TEST_PG_URL.

Ex.: NINF_TEST_PG_URL=postgresql+asyncpg://dev:dev@127.0.0.1:5439/app pytest tests/test_notifications.py
"""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routers import incidents as incidents_router
from app.core.dependencies import get_current_user
from app.database import Base
from app.models import (
    Asset,
    Incident,
    IncidentAction,
    Notification,
    PushSubscription,
    User,
    UserRole,
)
from app.services import notifications as svc

UTC = timezone.utc
# segunda-feira 10:00 em Brasília
MON = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)

# ---------- função pura ----------


@pytest.mark.parametrize(
    "window,start,expected",
    [
        ("critical", MON, MON + timedelta(minutes=15)),
        ("elevated", MON, MON + timedelta(hours=1)),
        ("standard", MON, MON + timedelta(hours=4)),
        # sexta 16:00 BRT + 4 h comerciais = segunda 10:00 BRT
        ("standard", datetime(2026, 11, 6, 19, 0, tzinfo=UTC), MON + timedelta(days=7)),
        # sábado 12:00 BRT: conta a partir de segunda 08:00 BRT
        (
            "standard",
            datetime(2026, 11, 7, 15, 0, tzinfo=UTC),
            MON + timedelta(days=7, hours=2),
        ),
        # 1 dia útil = 10 h comerciais: seg 10:00 -> ter 10:00 BRT
        ("no_client", MON, MON + timedelta(days=1)),
    ],
)
def test_response_deadline_table(window, start, expected):
    assert svc.response_deadline(window, start) == expected


def test_critical_is_24x7_and_standard_is_business_hours():
    sat = datetime(2026, 11, 7, 15, 0, tzinfo=UTC)
    assert svc.response_deadline("critical", sat) == sat + timedelta(minutes=15)
    assert svc.response_deadline("standard", sat) > sat + timedelta(days=1)


def test_next_escalation_only_after_window_without_ack():
    kw = dict(window="critical", step_at=MON, step=0, total=3, acknowledged=False)
    assert svc.next_escalation(now=MON + timedelta(minutes=14), **kw) is None
    assert svc.next_escalation(now=MON + timedelta(minutes=15), **kw) == 1
    assert (
        svc.next_escalation(
            now=MON + timedelta(hours=9), **{**kw, "acknowledged": True}
        )
        is None
    )
    assert (
        svc.next_escalation(now=MON + timedelta(hours=9), **{**kw, "step": 2}) is None
    )


def test_severity_window_map():
    assert svc.severity_window(5, True) == "critical"
    assert svc.severity_window(4, True) == "elevated"
    assert svc.severity_window(3, True) == "standard"
    assert svc.severity_window(5, False) == "no_client"
    assert svc.severity_window(2, True) is None


# ---------- Postgres ----------

URL = os.environ.get("NINF_TEST_PG_URL")
pg = pytest.mark.skipif(not URL, reason="NINF_TEST_PG_URL não definido")


@pytest_asyncio.fixture
async def maker(monkeypatch):
    engine = create_async_engine(URL)
    tabs = [
        t.__table__
        for t in (
            Asset,
            Incident,
            IncidentAction,
            User,
            PushSubscription,
            Notification,
        )
    ]
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=tabs))
    m = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(svc, "SessionLocal", m)
    monkeypatch.setattr(incidents_router, "SessionLocal", m)
    yield m
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
    await engine.dispose()


class Channels:
    """Dublê dos provedores; `fail` desliga um canal."""

    def __init__(self, monkeypatch, *, email_ok=True, push_ok=True):
        self.emails: list[dict] = []
        self.pushes: list[dict] = []
        outer = self

        class Email:
            @classmethod
            def from_settings(cls):
                return cls()

            async def send(self, **kw):
                if not email_ok:
                    raise RuntimeError("provider down")
                outer.emails.append(kw)
                return SimpleNamespace(email_id="em_1", attempts=1)

        async def push(sub, payload):
            if not push_ok:
                raise RuntimeError("push down")
            outer.pushes.append(payload)
            return True

        monkeypatch.setattr(svc, "ResendEmailClient", Email)
        monkeypatch.setattr(svc, "send_web_push", push)


async def _seed(maker, *, severity=5, tenant="acme", users=2):
    async with maker() as s:
        inc = Incident(
            fingerprint="f1",
            title="t",
            severity=severity,
            host_id="h",
            host_name="h",
            trigger_id="t",
            first_seen=MON,
            tags={"ninf_customer_name": tenant},
        )
        s.add(inc)
        roles = [UserRole.soc, UserRole.noc, UserRole.admin][:users]
        us = [
            User(email=f"u{i}@example.invalid", hashed_password="x", role=r)
            for i, r in enumerate(roles)
        ]
        s.add_all(us)
        await s.flush()
        for u in us:
            s.add(
                PushSubscription(
                    tenant_id=tenant,
                    user_id=u.id,
                    endpoint=f"https://push.example.invalid/{u.id}",
                    auth_key="a",
                    p256dh_key="p",
                )
            )
        await s.commit()
        return inc.id, [u.id for u in us]


async def _rows(maker):
    async with maker() as s:
        return (
            (await s.execute(select(Notification).order_by(Notification.id)))
            .scalars()
            .all()
        )


@pg
@pytest.mark.asyncio
async def test_email_failure_still_sends_push_and_records_error(maker, monkeypatch):
    ch = Channels(monkeypatch, email_ok=False)
    await _seed(maker)
    await svc.sweep(MON)
    rows = {r.channel: r for r in await _rows(maker)}
    assert len(ch.pushes) == 1
    assert rows["email"].sent_at is None
    assert rows["email"].provider_result.startswith("error:")
    assert rows["push"].sent_at is not None


@pg
@pytest.mark.asyncio
async def test_push_failure_still_sends_email(maker, monkeypatch):
    ch = Channels(monkeypatch, push_ok=False)
    await _seed(maker)
    await svc.sweep(MON)
    rows = {r.channel: r for r in await _rows(maker)}
    assert len(ch.emails) == 1
    assert rows["email"].sent_at is not None
    assert rows["push"].provider_result.startswith("error:")


@pg
@pytest.mark.asyncio
async def test_provider_accept_is_not_acknowledgement_and_message_is_minimal(
    maker, monkeypatch
):
    ch = Channels(monkeypatch)
    await _seed(maker)
    await svc.sweep(MON)
    rows = await _rows(maker)
    assert all(r.sent_at and r.provider_result for r in rows)
    assert all(r.acknowledged_at is None and r.ack_type is None for r in rows)
    assert all(r.resolved_at is None for r in rows)
    body = ch.emails[0]["text"]
    assert "#" in body and "severidade 5" in body and "Ação esperada" in body
    assert "acme" not in body and "acme" not in str(ch.pushes[0])


@pg
@pytest.mark.asyncio
async def test_sweep_is_idempotent_per_window_and_escalates_after(maker, monkeypatch):
    ch = Channels(monkeypatch)
    await _seed(maker)
    await svc.sweep(MON)
    await svc.sweep(MON + timedelta(minutes=5))
    await svc.sweep(MON + timedelta(minutes=14))
    assert len(await _rows(maker)) == 2 and len(ch.emails) == 1
    out = await svc.sweep(MON + timedelta(minutes=16))
    assert out["escalated"] == 1
    again = await svc.sweep(MON + timedelta(minutes=17))
    assert again == {"notified": 0, "escalated": 0}
    rows = await _rows(maker)
    assert {r.step for r in rows} == {0, 1} and len(rows) == 4
    assert len({r.user_id for r in rows}) == 2


@pg
@pytest.mark.asyncio
async def test_no_escalation_once_acknowledged(maker, monkeypatch):
    Channels(monkeypatch)
    await _seed(maker)
    await svc.sweep(MON)
    async with maker() as s:
        for r in (await s.execute(select(Notification))).scalars():
            r.acknowledged_at = MON
        await s.commit()
    assert (await svc.sweep(MON + timedelta(hours=3)))["escalated"] == 0


@pg
@pytest.mark.asyncio
async def test_recipients_respect_tenant_and_role(maker, monkeypatch):
    Channels(monkeypatch)
    async with maker() as s:
        s.add_all(
            [
                User(
                    email="a@example.invalid",
                    hashed_password="x",
                    role=UserRole.operator,
                    tenant_id="acme",
                ),
                User(
                    email="b@example.invalid",
                    hashed_password="x",
                    role=UserRole.operator,
                    tenant_id="other",
                ),
                User(
                    email="c@example.invalid",
                    hashed_password="x",
                    role=UserRole.cliente,
                    tenant_id="acme",
                ),
            ]
        )
        await s.commit()
        inc = Incident(
            fingerprint="f",
            title="t",
            severity=5,
            host_id="h",
            host_name="h",
            trigger_id="t",
            tags={"ninf_customer_name": "acme"},
        )
        got = [u.email for u in await svc._recipients(s, inc)]
    assert got == ["a@example.invalid"]


def _app(user):
    app = FastAPI()
    app.include_router(incidents_router.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@pg
@pytest.mark.asyncio
async def test_ack_authorized_sets_ack_not_resolution(maker, monkeypatch):
    Channels(monkeypatch)
    iid, (uid, _) = await _seed(maker)
    await svc.sweep(MON)
    user = SimpleNamespace(id=uid, role=UserRole.noc, tenant_id=None)
    async with _app(user) as c:
        r = await c.post(f"/api/incidents/{iid}/notifications/ack")
    assert r.status_code == 200 and r.json()["acknowledged"] == 2
    rows = await _rows(maker)
    assert all(x.acknowledged_at and x.ack_type == "manual" for x in rows)
    assert all(x.acknowledged_by_user_id == uid and x.resolved_at is None for x in rows)


@pg
@pytest.mark.asyncio
async def test_ack_wrong_tenant_or_role_is_denied_and_changes_nothing(
    maker, monkeypatch
):
    Channels(monkeypatch)
    iid, (uid, _) = await _seed(maker)
    await svc.sweep(MON)
    other = SimpleNamespace(id=99, role=UserRole.operator, tenant_id="other")
    viewer = SimpleNamespace(id=98, role=UserRole.viewer, tenant_id="acme")
    async with _app(other) as c:
        assert (
            await c.post(f"/api/incidents/{iid}/notifications/ack")
        ).status_code == 404
    async with _app(viewer) as c:
        assert (
            await c.post(f"/api/incidents/{iid}/notifications/ack")
        ).status_code == 403
    assert all(r.acknowledged_at is None for r in await _rows(maker))


@pg
@pytest.mark.asyncio
async def test_resolution_is_stamped_separately(maker, monkeypatch):
    Channels(monkeypatch)
    iid, _ = await _seed(maker)
    await svc.sweep(MON)
    async with maker() as s:
        (await s.get(Incident, iid)).status = "resolved"
        await s.commit()
    await svc.sweep(MON + timedelta(minutes=1))
    assert all(r.resolved_at and r.acknowledged_at is None for r in await _rows(maker))
