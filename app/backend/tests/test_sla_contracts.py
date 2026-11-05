"""Contratos/SLA editáveis: contas de calendário, resolução, sweep por contrato e API.

Parte pura roda sempre; o resto exige NINF_TEST_PG_URL (ver test_notifications.py).
"""

import logging
import os
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routers import contracts as contracts_router
from app.core.dependencies import get_current_user
from app.database import Base, get_db
from app.migrate import apply_sla_sql
from app.models import (
    Asset,
    Contract,
    ContractChange,
    EscalationStep,
    Incident,
    IncidentAction,
    Notification,
    PushSubscription,
    SlaCalendar,
    SlaCalendarHours,
    SlaHoliday,
    SlaPolicy,
    TenantMapping,
    User,
    UserRole,
)
from app.services import notifications as svc
from app.services.sla import (
    CalendarCfg,
    ContractCfg,
    PolicyCfg,
    SlaConfig,
    add_calendar_time,
    modality_divergences,
    resolve,
)
from tests.test_notifications import MON, Channels, _rows, _seed

UTC = timezone.utc
HOURS = {d: ((time(8), time(18)),) for d in range(5)}


def _cal(tz="America/Sao_Paulo", hours=HOURS, holidays=()):
    return CalendarCfg(tz, False, hours, frozenset(holidays))


# ---------- add_calendar_time (puro) ----------


def test_weekend_is_skipped():
    # sexta 17:00 BRT + 2 h -> segunda 09:00 BRT
    fri = datetime(2026, 11, 6, 20, 0, tzinfo=UTC)
    assert add_calendar_time(fri, timedelta(hours=2), _cal()) == datetime(
        2026, 11, 9, 12, 0, tzinfo=UTC
    )


def test_registered_holiday_is_skipped():
    # 02/11 é segunda; cadastrado como feriado, o prazo de 1 h aberto na sexta 17:30
    # BRT vence terça 08:30 (30 min na sexta + 30 min na terça)
    fri = datetime(2026, 11, 6, 20, 30, tzinfo=UTC)
    cal = _cal(holidays=[date(2026, 11, 9)])
    assert add_calendar_time(fri, timedelta(hours=1), cal) == datetime(
        2026, 11, 10, 11, 30, tzinfo=UTC
    )
    assert add_calendar_time(fri, timedelta(hours=1), _cal()) == datetime(
        2026, 11, 9, 11, 30, tzinfo=UTC
    )


def test_day_rollover_and_multiple_intervals_per_day():
    lunch = _cal(
        hours={d: ((time(8), time(12)), (time(13), time(18))) for d in range(5)}
    )
    # segunda 11:00 BRT + 2 h: 1 h até 12:00, almoço, 1 h a partir de 13:00 -> 14:00
    start = datetime(2026, 11, 2, 14, 0, tzinfo=UTC)
    assert add_calendar_time(start, timedelta(hours=2), lunch) == datetime(
        2026, 11, 2, 17, 0, tzinfo=UTC
    )
    # virada de dia: segunda 17:00 BRT + 2 h -> terça 09:00 BRT
    mon = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)
    assert add_calendar_time(mon, timedelta(hours=2), _cal()) == datetime(
        2026, 11, 3, 12, 0, tzinfo=UTC
    )


def test_timezone_comes_from_calendar_not_fixed_utc_minus_3():
    # Nova York em novembro (EST, UTC-5): 08:00 local = 13:00 UTC
    ny = _cal("America/New_York")
    start = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)  # 07:00 local, antes de abrir
    assert add_calendar_time(start, timedelta(hours=1), ny) == datetime(
        2026, 11, 2, 14, 0, tzinfo=UTC
    )


def test_24x7_adds_directly():
    sat = datetime(2026, 11, 7, 15, 0, tzinfo=UTC)
    cal = CalendarCfg("America/Sao_Paulo", True, {}, frozenset())
    assert add_calendar_time(sat, timedelta(minutes=90), cal) == sat + timedelta(
        minutes=90
    )


def test_calendar_without_working_time_fails_instead_of_looping():
    with pytest.raises(ValueError):
        add_calendar_time(MON, timedelta(hours=1), _cal(hours={}))


# ---------- resolução (puro) ----------

H24 = CalendarCfg("America/Sao_Paulo", True, {}, frozenset())


def _p(cid, key, sev, ack, has_tenant=True, min_sev=None):
    return PolicyCfg(cid, key, min_sev, sev, has_tenant, timedelta(minutes=ack), H24)


ROLES = (UserRole.soc, UserRole.noc)


def _c(cid, tenant, policies, *, default=False, starts=None, ends=None):
    return ContractCfg(
        cid, tenant, default, not default, starts, ends, "America/Sao_Paulo",
        tuple(policies), ROLES,
    )  # fmt: skip


DEFAULT = _c(
    1,
    None,
    [
        _p(1, "critical", 5, 15),
        _p(1, "elevated", 4, 60),
        _p(1, "no_client", None, 600, False, 4),
    ],
    default=True,
)


def test_resolution_tenant_active_contract_then_default():
    own = _c(2, "acme", [_p(2, "critical", 5, 5)])
    cfg = SlaConfig((DEFAULT, own))
    c, p = resolve(cfg, "acme", 5, MON)
    assert (c.id, p.ack) == (2, timedelta(minutes=5))
    c, p = resolve(cfg, "other", 5, MON)
    assert (c.id, p.ack) == (1, timedelta(minutes=15))
    c, p = resolve(cfg, "", 5, MON)  # sem cliente
    assert (c.id, p.key) == (1, "no_client")


def test_contract_outside_validity_falls_back_to_default():
    own = _c(2, "acme", [_p(2, "critical", 5, 5)], starts=date(2026, 12, 1))
    ended = _c(3, "beta", [_p(3, "critical", 5, 5)], ends=date(2026, 10, 31))
    cfg = SlaConfig((DEFAULT, own, ended))
    assert resolve(cfg, "acme", 5, MON)[0].id == 1
    assert resolve(cfg, "beta", 5, MON)[0].id == 1


def test_contract_without_policy_for_class_falls_back_with_warning(caplog):
    own = _c(2, "acme", [_p(2, "critical", 5, 5)])
    with caplog.at_level(logging.WARNING, logger="nessops.sla"):
        c, p = resolve(SlaConfig((DEFAULT, own)), "acme", 4, MON)
    assert (c.id, p.ack) == (1, timedelta(minutes=60))
    assert "sem política habilitada" in caplog.text


def test_no_default_and_no_contract_resolves_nothing():
    assert resolve(SlaConfig(()), "acme", 5, MON) is None


def test_modality_divergence_is_reported_without_writes():
    out = modality_divergences(
        [("acme", "managed"), ("beta", "shared"), ("gama", None)],
        [("acme", "onsite"), ("beta", "shared"), ("acme", None), ("gama", "managed")],
    )
    assert out == [
        {"tenant_id": "acme", "contract_modality": "managed", "mapping_modality": None},
        {"tenant_id": "acme", "contract_modality": "managed", "mapping_modality": "onsite"},
    ]  # fmt: skip


# ---------- Postgres ----------

URL = os.environ.get("NINF_TEST_PG_URL")
pg = pytest.mark.skipif(not URL, reason="NINF_TEST_PG_URL não definido")
TABLES = (
    Asset,
    Incident,
    IncidentAction,
    User,
    PushSubscription,
    Notification,
    SlaCalendar,
    SlaCalendarHours,
    SlaHoliday,
    Contract,
    SlaPolicy,
    EscalationStep,
    ContractChange,
    TenantMapping,
)


@pytest_asyncio.fixture
async def maker(monkeypatch):
    engine = create_async_engine(URL)
    tabs = [t.__table__ for t in TABLES]
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=tabs))
        await apply_sla_sql(c)
    m = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(svc, "SessionLocal", m)
    yield m
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
    await engine.dispose()


async def _count(maker, model):
    async with maker() as s:
        return await s.scalar(select(func.count()).select_from(model))


async def _default_id(s):
    return await s.scalar(select(Contract.id).where(Contract.is_default))


async def _tenant_contract(maker, tenant="acme", *, ack=30, status="active", **kw):
    async with maker() as s:
        cal = await s.scalar(select(SlaCalendar.id).where(SlaCalendar.name == "24x7"))
        c = Contract(tenant_id=tenant, name="c", status=status, calendar_id=cal, **kw)
        s.add(c)
        await s.flush()
        s.add(
            SlaPolicy(
                contract_id=c.id, key="critical", name="x", severity=5,
                has_tenant=True, ack_minutes=ack, calendar_id=cal,
            )
        )  # fmt: skip
        s.add(EscalationStep(contract_id=c.id, position=1, role="soc"))
        s.add(EscalationStep(contract_id=c.id, position=2, role="noc"))
        await s.commit()
        return c.id


@pg
@pytest.mark.asyncio
async def test_seed_is_idempotent_and_default_is_not_contractual(maker):
    async def snap():
        return [
            await _count(maker, m)
            for m in (
                Contract,
                SlaPolicy,
                EscalationStep,
                SlaCalendar,
                SlaCalendarHours,
            )
        ]

    first = await snap()
    async with maker() as s:
        conn = await s.connection()
        await apply_sla_sql(conn)
        await s.commit()
    assert first == await snap() == [1, 3, 4, 2, 5]
    async with maker() as s:
        d = (await s.execute(select(Contract))).scalar_one()
        assert d.is_default and not d.contractual and d.tenant_id is None
        pol = {p.key: p for p in (await s.execute(select(SlaPolicy))).scalars()}
    assert [pol[k].ack_minutes for k in ("critical", "elevated", "no_client")] == [
        15, 60, 600,
    ]  # fmt: skip


@pg
@pytest.mark.asyncio
async def test_sweep_with_seeded_values_matches_previous_behavior(maker, monkeypatch):
    ch = Channels(monkeypatch)
    await _seed(maker)
    await svc.sweep(MON)
    assert len(ch.emails) == 1
    assert (await svc.sweep(MON + timedelta(minutes=14)))["escalated"] == 0
    assert (await svc.sweep(MON + timedelta(minutes=16)))["escalated"] == 1


@pg
@pytest.mark.asyncio
async def test_editing_ack_minutes_in_db_changes_escalation_next_cycle(
    maker, monkeypatch
):
    Channels(monkeypatch)
    await _seed(maker)
    await svc.sweep(MON)
    assert (await svc.sweep(MON + timedelta(minutes=6)))["escalated"] == 0
    async with maker() as s:
        await s.execute(
            update(SlaPolicy).where(SlaPolicy.key == "critical").values(ack_minutes=5)
        )
        await s.commit()
    assert (await svc.sweep(MON + timedelta(minutes=7)))["escalated"] == 1


@pg
@pytest.mark.asyncio
async def test_disabled_policy_does_not_notify(maker, monkeypatch):
    ch = Channels(monkeypatch)
    await _seed(maker, severity=5)
    async with maker() as s:
        await s.execute(
            update(SlaPolicy).where(SlaPolicy.key == "critical").values(enabled=False)
        )
        await s.commit()
    assert await svc.sweep(MON) == {"notified": 0, "escalated": 0}
    assert not ch.emails


@pg
@pytest.mark.asyncio
async def test_no_enabled_policy_does_not_notify_and_logs_warning(
    maker, monkeypatch, caplog
):
    ch = Channels(monkeypatch)
    await _seed(maker)
    async with maker() as s:
        await s.execute(update(SlaPolicy).values(enabled=False))
        await s.commit()
    with caplog.at_level(logging.WARNING, logger="nessops.notifications"):
        assert await svc.sweep(MON) == {"notified": 0, "escalated": 0}
    assert not ch.emails and "Nenhuma política de SLA habilitada" in caplog.text


@pg
@pytest.mark.asyncio
async def test_sweep_uses_the_contract_of_the_incident_tenant(maker, monkeypatch):
    Channels(monkeypatch)
    await _tenant_contract(maker, "acme", ack=30)
    await _seed(maker, tenant="acme")
    await svc.sweep(MON)
    # padrão (15 min) escalaria aqui; o contrato do tenant (30 min) ainda não
    assert (await svc.sweep(MON + timedelta(minutes=16)))["escalated"] == 0
    assert (await svc.sweep(MON + timedelta(minutes=31)))["escalated"] == 1


@pg
@pytest.mark.asyncio
async def test_other_tenant_and_inactive_contract_use_the_default(maker, monkeypatch):
    Channels(monkeypatch)
    await _tenant_contract(maker, "acme", ack=30, status="suspended")
    await _seed(maker, tenant="acme")
    await svc.sweep(MON)
    assert (await svc.sweep(MON + timedelta(minutes=16)))["escalated"] == 1


@pg
@pytest.mark.asyncio
async def test_disabled_escalation_step_is_skipped(maker, monkeypatch):
    Channels(monkeypatch)
    await _seed(maker, users=3)  # soc, noc, admin
    async with maker() as s:
        await s.execute(
            update(EscalationStep)
            .where(EscalationStep.role == "noc")
            .values(enabled=False)
        )
        await s.commit()
    await svc.sweep(MON)
    await svc.sweep(MON + timedelta(minutes=16))
    async with maker() as s:
        roles = {u.id: u.role for u in (await s.execute(select(User))).scalars()}
    assert {roles[r.user_id] for r in await _rows(maker)} == {
        UserRole.soc, UserRole.admin
    }  # fmt: skip


@pg
@pytest.mark.asyncio
async def test_contract_without_steps_uses_default_steps(maker, monkeypatch):
    Channels(monkeypatch)
    cid = await _tenant_contract(maker, "acme", ack=30)
    async with maker() as s:
        await s.execute(
            update(EscalationStep)
            .where(EscalationStep.contract_id == cid)
            .values(enabled=False)
        )
        await s.commit()
    await _seed(maker, tenant="acme")
    await svc.sweep(MON)
    async with maker() as s:
        soc = await s.scalar(select(User.id).where(User.role == UserRole.soc))
    assert {r.user_id for r in await _rows(maker)} == {soc}  # 1º passo do padrão


@pg
@pytest.mark.asyncio
async def test_sweep_honors_longer_contract_window_over_default(
    maker, monkeypatch
):
    """Contrato com 120 min não escala aos 60: o padrão (15 min) já teria escalado."""
    Channels(monkeypatch)
    await _tenant_contract(maker, "acme", ack=120)
    await _seed(maker, tenant="acme")
    await svc.sweep(MON)
    assert (await svc.sweep(MON + timedelta(minutes=60)))["escalated"] == 0


# ---------- API ----------


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


POLICY = {
    "key": "critical", "name": "Crítica", "severity": 5, "has_tenant": True,
    "ack_minutes": 20, "enabled": True,
}  # fmt: skip
BASE = "/api/v1/sla"


@pg
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role", [UserRole.viewer, UserRole.cliente, UserRole.helpdesk, UserRole.gestao]
)
async def test_api_read_forbidden_for_viewer_and_client(maker, role):
    async with _api(maker, role, "acme") as c:
        assert (await c.get(f"{BASE}/contracts")).status_code == 403
        assert (await c.get(f"{BASE}/calendars")).status_code == 403


@pg
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role", [UserRole.operator, UserRole.noc, UserRole.viewer, UserRole.cliente]
)
async def test_api_write_forbidden_below_admin(maker, role):
    async with _api(maker, role) as c:
        r = await c.post(f"{BASE}/contracts", json={"tenant_id": "a", "name": "n"})
        assert r.status_code == 403
        assert (
            await c.put(f"{BASE}/contracts/1/policies/critical", json=POLICY)
        ).status_code == 403
        assert (
            await c.post(f"{BASE}/contracts/1/status", json={"status": "ended"})
        ).status_code == 403
        assert (await c.delete(f"{BASE}/calendars/1")).status_code == 403
        assert (await c.put(f"{BASE}/contracts/1/escalation-steps/1", json={"position": 1, "role": "soc"})).status_code == 403  # fmt: skip


@pg
@pytest.mark.asyncio
async def test_api_operator_reads_default_marked_not_contractual(maker):
    async with _api(maker, UserRole.operator) as c:
        body = (await c.get(f"{BASE}/contracts")).json()
        assert [(x["is_default"], x["contractual"]) for x in body] == [(True, False)]
        det = (await c.get(f"{BASE}/contracts/{body[0]['id']}")).json()
        assert det["contractual"] is False and len(det["policies"]) == 3
        assert (await c.get(f"{BASE}/contracts/999")).status_code == 404


@pg
@pytest.mark.asyncio
async def test_api_contract_lifecycle_transitions_and_conflicts(maker):
    async with _api(maker, UserRole.admin) as c:
        cal = (await c.get(f"{BASE}/calendars")).json()[0]["id"]
        new = await c.post(
            f"{BASE}/contracts",
            json={"tenant_id": "acme", "name": "Acme", "modality": "managed", "calendar_id": cal},
        )  # fmt: skip
        assert new.status_code == 201 and new.json()["status"] == "draft"
        cid = new.json()["id"]

        def st(s, i=cid):
            return c.post(f"{BASE}/contracts/{i}/status", json={"status": s})

        assert (await st("suspended")).status_code == 409  # draft -> suspended
        assert (await st("active")).status_code == 409  # sem política
        assert (await c.put(f"{BASE}/contracts/{cid}/policies/critical", json=POLICY)).status_code == 200  # fmt: skip
        assert (await st("active")).status_code == 200
        # segundo contrato ativo do mesmo tenant
        other = (await c.post(f"{BASE}/contracts", json={"tenant_id": "acme", "name": "B", "calendar_id": cal})).json()["id"]  # fmt: skip
        await c.put(f"{BASE}/contracts/{other}/policies/critical", json=POLICY)
        assert (await st("active", other)).status_code == 409
        assert (await st("suspended")).status_code == 200
        assert (await st("active")).status_code == 200
        assert (await st("ended")).status_code == 200
        assert (await st("active")).status_code == 409  # ended é final
        assert (await c.put(f"{BASE}/contracts/{cid}", json={"name": "x"})).status_code == 409  # fmt: skip
        d = (await c.get(f"{BASE}/contracts")).json()
        assert next(x for x in d if x["id"] == cid)["status"] == "ended"
        # padrão não muda de status
        did = next(x["id"] for x in d if x["is_default"])
        assert (await st("suspended", did)).status_code == 409


@pg
@pytest.mark.asyncio
async def test_api_active_contract_change_writes_audit_row(maker):
    async with _api(maker, UserRole.admin) as c:
        did = (await c.get(f"{BASE}/contracts")).json()[0]["id"]
        before = await _count(maker, ContractChange)
        r = await c.put(f"{BASE}/contracts/{did}/policies/critical", json={**POLICY, "ack_minutes": 20})  # fmt: skip
        assert r.status_code == 200 and r.json()["updated_by_user_id"] == 7
        rows = (await c.get(f"{BASE}/contracts/{did}/changes")).json()
    assert before == 0 and len(rows) == 1
    ch = rows[0]
    assert (ch["entity"], ch["changed_by_user_id"]) == ("policy", 7)
    assert ch["before"]["ack_minutes"] == 15 and ch["after"]["ack_minutes"] == 20


@pg
@pytest.mark.asyncio
async def test_api_draft_change_has_no_audit_row_but_is_saved(maker):
    async with _api(maker, UserRole.admin) as c:
        cid = (await c.post(f"{BASE}/contracts", json={"tenant_id": "z", "name": "z"})).json()["id"]  # fmt: skip
        assert (await c.put(f"{BASE}/contracts/{cid}/policies/critical", json=POLICY)).status_code == 200  # fmt: skip
    assert await _count(maker, ContractChange) == 0


@pg
@pytest.mark.asyncio
async def test_api_validation_422_and_calendar_in_use_409(maker):
    async with _api(maker, UserRole.admin) as c:
        did = (await c.get(f"{BASE}/contracts")).json()[0]["id"]
        for bad in ({"ack_minutes": 0}, {"ack_minutes": 43201}, {"tto_minutes": 0}, {"severity": 9}):  # fmt: skip
            r = await c.put(f"{BASE}/contracts/{did}/policies/critical", json={**POLICY, **bad})  # fmt: skip
            assert r.status_code == 422, bad
        cals = (await c.get(f"{BASE}/calendars")).json()
        biz = next(x for x in cals if x["name"] == "comercial")
        assert (await c.put(f"{BASE}/calendars/{biz['id']}", json={"name": "comercial", "timezone": "Marte/Olimpo"})).status_code == 422  # fmt: skip
        assert (await c.put(f"{BASE}/calendars/{biz['id']}/hours", json=[{"weekday": 7, "start_time": "08:00", "end_time": "18:00"}])).status_code == 422  # fmt: skip
        assert (await c.put(f"{BASE}/calendars/{biz['id']}/hours", json=[{"weekday": 1, "start_time": "18:00", "end_time": "08:00"}])).status_code == 422  # fmt: skip
        assert (await c.delete(f"{BASE}/calendars/{biz['id']}")).status_code == 409
        assert (await c.delete(f"{BASE}/calendars/999")).status_code == 404
        r = await c.post(f"{BASE}/contracts/{did}/policies/x", json=POLICY)
        assert r.status_code == 405
        assert (await c.put(f"{BASE}/contracts/{did}/policies/other", json=POLICY)).status_code == 422  # fmt: skip
        r = await c.put(f"{BASE}/contracts/{did}/escalation-steps/1", json={"position": 1, "role": "chefe"})  # fmt: skip
        assert r.status_code == 422


@pg
@pytest.mark.asyncio
async def test_api_holiday_and_hours_edit_change_the_calendar_used_by_the_sweep(
    maker, monkeypatch
):
    Channels(monkeypatch)
    async with _api(maker, UserRole.admin) as c:
        cals = (await c.get(f"{BASE}/calendars")).json()
        biz = next(x for x in cals if x["name"] == "comercial")["id"]
        h = await c.put(f"{BASE}/calendars/{biz}/holidays/2026-11-09", json={"holiday_date": "2026-11-09", "name": "Teste"})  # fmt: skip
        assert h.status_code == 200
        assert (await c.put(f"{BASE}/calendars/{biz}/holidays/2026-11-09", json={"holiday_date": "2026-11-10", "name": "x"})).status_code == 422  # fmt: skip
        # vários intervalos por dia
        assert (await c.put(f"{BASE}/calendars/{biz}/hours", json=[{"weekday": 0, "start_time": "08:00", "end_time": "12:00"}, {"weekday": 0, "start_time": "13:00", "end_time": "18:00"}])).status_code == 200  # fmt: skip
    from app.services.sla import load_config

    async with maker() as s:
        cfg = await load_config(s)
    cal = cfg.default.policies[2].calendar
    assert date(2026, 11, 9) in cal.holidays and len(cal.hours[0]) == 2
    # a trilha do contrato ativo (padrão) registrou as duas mudanças de calendário
    assert await _count(maker, ContractChange) == 2


@pg
@pytest.mark.asyncio
async def test_api_cannot_disable_last_default_step_or_policy(maker):
    async with _api(maker, UserRole.admin) as c:
        did = (await c.get(f"{BASE}/contracts")).json()[0]["id"]
        for pos in (1, 2, 3):
            r = await c.put(f"{BASE}/contracts/{did}/escalation-steps/{pos}", json={"position": pos, "role": "soc", "enabled": False})  # fmt: skip
            assert r.status_code == 200
        r = await c.put(f"{BASE}/contracts/{did}/escalation-steps/4", json={"position": 4, "role": "admin", "enabled": False})  # fmt: skip
        assert r.status_code == 409
        assert (await c.delete(f"{BASE}/contracts/{did}/escalation-steps/4")).status_code == 409  # fmt: skip
        for key in ("critical", "elevated"):
            assert (await c.delete(f"{BASE}/contracts/{did}/policies/{key}")).status_code == 204  # fmt: skip
        assert (await c.delete(f"{BASE}/contracts/{did}/policies/no_client")).status_code == 409  # fmt: skip


@pg
@pytest.mark.asyncio
async def test_api_modality_divergence_between_contract_and_mapping(maker):
    async with maker() as s:
        s.add(TenantMapping(internal_customer_id="acme", external_platform="zabbix", external_customer_id="1", modality="onsite"))  # fmt: skip
        await s.commit()
    await _tenant_contract(maker, "acme", modality="managed")
    async with _api(maker, UserRole.operator) as c:
        out = (await c.get(f"{BASE}/contracts/modality-divergences")).json()
    assert out == [{"tenant_id": "acme", "contract_modality": "managed", "mapping_modality": "onsite"}]  # fmt: skip


@pg
@pytest.mark.asyncio
async def test_db_constraints_two_active_per_tenant_and_single_default(maker):
    await _tenant_contract(maker, "acme")
    with pytest.raises(Exception):
        await _tenant_contract(maker, "acme")
    async with maker() as s:
        with pytest.raises(Exception):
            await s.execute(text(
                "INSERT INTO n_infraops_contracts (is_default, contractual, name, status)"
                " VALUES (TRUE, FALSE, 'outro', 'active')"
            ))  # fmt: skip
