"""Contratos, políticas de SLA, passos de escalonamento, calendários e feriados.

GET: operator ou superior. Escrita: admin/platform_admin. Cliente/viewer: 403.
Toda mudança em contrato ATIVO grava uma linha em n_infraops_contract_changes e um log
estruturado com antes/depois (só campos de configuração, sem dados sensíveis).
"""

from __future__ import annotations

import logging
from datetime import date, time
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_admin, require_operator
from app.database import get_db
from app.models import (
    Contract,
    ContractChange,
    EscalationStep,
    SlaCalendar,
    SlaCalendarHours,
    SlaHoliday,
    SlaPolicy,
    TenantMapping,
    User,
    UserRole,
)
from app.services.sla import modality_divergences

logger = logging.getLogger("nessops.api.contracts")
router = APIRouter(prefix="/api/v1/sla", tags=["sla-contracts"])

Minutes = Field(ge=1, le=43200)
Modality = Literal["managed", "onsite", "shared"]
# draft→active→suspended↔active→ended; ended é final.
TRANSITIONS = {
    "draft": {"active", "ended"},
    "active": {"suspended", "ended"},
    "suspended": {"active", "ended"},
    "ended": set(),
}


def _tz(v: str) -> str:
    try:
        ZoneInfo(v)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ValueError("timezone inválido")
    return v


class CalendarIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    timezone: str = "America/Sao_Paulo"
    is_24x7: bool = False

    _tz = field_validator("timezone")(lambda v: _tz(v))


class HoursIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _order(self):
        if not self.start_time < self.end_time:
            raise ValueError("start_time deve ser menor que end_time")
        return self


class HolidayIn(BaseModel):
    holiday_date: date
    name: str = Field(min_length=1, max_length=128)


class ContractIn(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    modality: Modality | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    calendar_id: int | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _dates(self):
        if self.starts_on and self.ends_on and self.starts_on > self.ends_on:
            raise ValueError("starts_on deve ser <= ends_on")
        return self


class ContractPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    modality: Modality | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    calendar_id: int | None = None
    notes: str | None = None


class StatusIn(BaseModel):
    status: Literal["draft", "active", "suspended", "ended"]


class PolicyIn(BaseModel):
    key: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    min_severity: int | None = Field(default=None, ge=0, le=5)
    severity: int | None = Field(default=None, ge=0, le=5)
    has_tenant: bool | None = None
    ack_minutes: int = Minutes
    # ponytail: tto/ttr só armazenados; o SLM do GLPI (etapa futura) lê do contrato.
    tto_minutes: int | None = Field(default=None, ge=1, le=43200)
    ttr_minutes: int | None = Field(default=None, ge=1, le=43200)
    calendar_id: int | None = None
    enabled: bool = True


class StepIn(BaseModel):
    position: int = Field(ge=1, le=100)
    role: UserRole
    enabled: bool = True


def _row(obj: Any) -> dict[str, Any]:
    return {
        c.key: (v.isoformat() if hasattr(v, "isoformat") else v)
        for c in obj.__table__.columns
        for v in [getattr(obj, c.key)]
    }


def _contract_out(c: Contract) -> dict[str, Any]:
    d = _row(c)
    # Qualquer saída com prazo carrega a marca: o padrão interno NÃO é contratual.
    d["contractual"] = bool(c.contractual)
    return d


async def _get(db: AsyncSession, model, id_: int, what: str):
    obj = await db.get(model, id_)
    if obj is None:
        raise HTTPException(404, f"{what} não encontrado")
    return obj


async def _audit(
    db: AsyncSession,
    contract: Contract,
    user: User,
    entity: str,
    before: dict | None,
    after: dict | None,
) -> None:
    """Trilha só para contrato ativo; sempre log estruturado do antes/depois."""
    logger.info(
        "sla_change",
        extra={
            "contract_id": contract.id,
            "entity": entity,
            "user_id": user.id,
            "before": before,
            "after": after,
        },
    )
    if contract.status == "active":
        db.add(
            ContractChange(
                contract_id=contract.id,
                changed_by_user_id=user.id,
                entity=entity,
                before=before,
                after=after,
            )
        )


async def _commit(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Conflito de integridade") from exc


async def _check_calendar(db: AsyncSession, cid: int | None) -> None:
    if cid is not None:
        await _get(db, SlaCalendar, cid, "Calendário")


async def _mutable(db: AsyncSession, contract_id: int) -> Contract:
    c = await _get(db, Contract, contract_id, "Contrato")
    if c.status == "ended":
        raise HTTPException(409, "Contrato encerrado é imutável")
    return c


# ---------- contratos ----------


@router.get("/contracts")
async def list_contracts(
    _: User = Depends(require_operator), db: AsyncSession = Depends(get_db)
):
    rows = (await db.execute(select(Contract).order_by(Contract.id))).scalars().all()
    return [_contract_out(c) for c in rows]


@router.get("/contracts/modality-divergences")
async def get_modality_divergences(
    _: User = Depends(require_operator), db: AsyncSession = Depends(get_db)
):
    """Contrato ativo x mapeamento (pipeline_health). Só leitura."""
    contracts = (
        await db.execute(
            select(Contract.tenant_id, Contract.modality).where(
                Contract.status == "active", Contract.tenant_id.is_not(None)
            )
        )
    ).all()
    mappings = (
        await db.execute(
            select(TenantMapping.internal_customer_id, TenantMapping.modality)
        )
    ).all()
    return modality_divergences(contracts, mappings)


@router.get("/contracts/{contract_id}")
async def get_contract(
    contract_id: int,
    _: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    c = await _get(db, Contract, contract_id, "Contrato")
    pols = (
        (
            await db.execute(
                select(SlaPolicy)
                .where(SlaPolicy.contract_id == c.id)
                .order_by(SlaPolicy.id)
            )
        )
        .scalars()
        .all()
    )
    steps = (
        (
            await db.execute(
                select(EscalationStep)
                .where(EscalationStep.contract_id == c.id)
                .order_by(EscalationStep.position)
            )
        )
        .scalars()
        .all()
    )
    return {
        **_contract_out(c),
        "policies": [_row(p) for p in pols],
        "escalation_steps": [_row(s) for s in steps],
    }


@router.get("/contracts/{contract_id}/changes")
async def list_changes(
    contract_id: int,
    _: User = Depends(require_operator),
    db: AsyncSession = Depends(get_db),
):
    await _get(db, Contract, contract_id, "Contrato")
    rows = (
        (
            await db.execute(
                select(ContractChange)
                .where(ContractChange.contract_id == contract_id)
                .order_by(ContractChange.id)
            )
        )
        .scalars()
        .all()
    )
    return [_row(r) for r in rows]


@router.post("/contracts", status_code=201)
async def create_contract(
    body: ContractIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _check_calendar(db, body.calendar_id)
    c = Contract(
        **body.model_dump(),
        status="draft",
        contractual=True,
        is_default=False,
        updated_by_user_id=user.id,
    )
    db.add(c)
    await _commit(db)
    logger.info("contract_created", extra={"contract_id": c.id, "user_id": user.id})
    return _contract_out(c)


@router.put("/contracts/{contract_id}")
async def update_contract(
    contract_id: int,
    body: ContractPatch,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    c = await _mutable(db, contract_id)
    patch = body.model_dump(exclude_unset=True)
    if "calendar_id" in patch:
        await _check_calendar(db, patch["calendar_id"])
        if c.status == "active" and patch["calendar_id"] is None:
            raise HTTPException(409, "Contrato ativo exige calendário")
    before = _row(c)
    for k, v in patch.items():
        setattr(c, k, v)
    if c.starts_on and c.ends_on and c.starts_on > c.ends_on:
        raise HTTPException(422, "starts_on deve ser <= ends_on")
    c.updated_by_user_id = user.id
    await db.flush()
    await _audit(db, c, user, "contract", before, _row(c))
    await _commit(db)
    return _contract_out(c)


@router.post("/contracts/{contract_id}/status")
async def change_status(
    contract_id: int,
    body: StatusIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    c = await _get(db, Contract, contract_id, "Contrato")
    if c.is_default:
        raise HTTPException(409, "O padrão interno não muda de status")
    if body.status not in TRANSITIONS[c.status]:
        raise HTTPException(409, f"Transição inválida: {c.status} -> {body.status}")
    if body.status == "active":
        if c.calendar_id is None:
            raise HTTPException(409, "Ativar exige calendário")
        enabled = await db.scalar(
            select(func.count())
            .select_from(SlaPolicy)
            .where(SlaPolicy.contract_id == c.id, SlaPolicy.enabled.is_(True))
        )
        if not enabled:
            raise HTTPException(409, "Ativar exige ao menos uma política habilitada")
    before = _row(c)
    c.status = body.status
    c.updated_by_user_id = user.id
    try:
        await db.flush()
    except IntegrityError as exc:  # uq_contracts_tenant_active
        await db.rollback()
        raise HTTPException(409, "Já existe contrato ativo para este tenant") from exc
    # a transição de/para ativo também entra na trilha
    db.add(
        ContractChange(
            contract_id=c.id,
            changed_by_user_id=user.id,
            entity="status",
            before={"status": before["status"]},
            after={"status": c.status},
        )
    )
    logger.info(
        "contract_status",
        extra={"contract_id": c.id, "user_id": user.id, "to": c.status},
    )
    await _commit(db)
    return _contract_out(c)


# ---------- políticas ----------


async def _validate_policy(db: AsyncSession, body: PolicyIn) -> None:
    await _check_calendar(db, body.calendar_id)


@router.put("/contracts/{contract_id}/policies/{key}")
async def upsert_policy(
    contract_id: int,
    key: str,
    body: PolicyIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if body.key != key:
        raise HTTPException(422, "key do corpo difere da URL")
    c = await _mutable(db, contract_id)
    await _validate_policy(db, body)
    p = (
        await db.execute(
            select(SlaPolicy).where(SlaPolicy.contract_id == c.id, SlaPolicy.key == key)
        )
    ).scalar_one_or_none()
    before = _row(p) if p else None
    if p is None:
        p = SlaPolicy(contract_id=c.id)
        db.add(p)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    p.updated_by_user_id = user.id
    await db.flush()
    if c.status == "active" and not await _has_enabled_policy(db, c.id):
        await db.rollback()
        raise HTTPException(
            409, "Contrato ativo exige ao menos uma política habilitada"
        )
    await _audit(db, c, user, "policy", before, _row(p))
    await _commit(db)
    return _row(p)


async def _has_enabled_policy(db: AsyncSession, contract_id: int) -> bool:
    return bool(
        await db.scalar(
            select(func.count())
            .select_from(SlaPolicy)
            .where(SlaPolicy.contract_id == contract_id, SlaPolicy.enabled.is_(True))
        )
    )


@router.delete("/contracts/{contract_id}/policies/{key}", status_code=204)
async def delete_policy(
    contract_id: int,
    key: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    c = await _mutable(db, contract_id)
    p = (
        await db.execute(
            select(SlaPolicy).where(SlaPolicy.contract_id == c.id, SlaPolicy.key == key)
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(404, "Política não encontrada")
    before = _row(p)
    await db.delete(p)
    await db.flush()
    if c.status == "active" and not await _has_enabled_policy(db, c.id):
        await db.rollback()
        raise HTTPException(
            409, "Contrato ativo exige ao menos uma política habilitada"
        )
    await _audit(db, c, user, "policy", before, None)
    await _commit(db)


# ---------- passos de escalonamento ----------


async def _enabled_steps(db: AsyncSession, contract_id: int) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(EscalationStep)
            .where(
                EscalationStep.contract_id == contract_id,
                EscalationStep.enabled.is_(True),
            )
        )
        or 0
    )


@router.put("/contracts/{contract_id}/escalation-steps/{position}")
async def upsert_step(
    contract_id: int,
    position: int,
    body: StepIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if body.position != position:
        raise HTTPException(422, "position do corpo difere da URL")
    c = await _mutable(db, contract_id)
    s = (
        await db.execute(
            select(EscalationStep).where(
                EscalationStep.contract_id == c.id,
                EscalationStep.position == position,
            )
        )
    ).scalar_one_or_none()
    before = _row(s) if s else None
    if s is None:
        s = EscalationStep(contract_id=c.id)
        db.add(s)
    s.position, s.role, s.enabled = body.position, body.role.value, body.enabled
    s.updated_by_user_id = user.id
    await db.flush()
    # Sem passo habilitado o contrato usa os do padrão; o padrão em si exige >= 1.
    if c.is_default and not await _enabled_steps(db, c.id):
        await db.rollback()
        raise HTTPException(409, "O padrão exige ao menos um passo habilitado")
    await _audit(db, c, user, "escalation_step", before, _row(s))
    await _commit(db)
    return _row(s)


@router.delete("/contracts/{contract_id}/escalation-steps/{position}", status_code=204)
async def delete_step(
    contract_id: int,
    position: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    c = await _mutable(db, contract_id)
    s = (
        await db.execute(
            select(EscalationStep).where(
                EscalationStep.contract_id == c.id,
                EscalationStep.position == position,
            )
        )
    ).scalar_one_or_none()
    if s is None:
        raise HTTPException(404, "Passo não encontrado")
    before = _row(s)
    await db.delete(s)
    await db.flush()
    if c.is_default and not await _enabled_steps(db, c.id):
        await db.rollback()
        raise HTTPException(409, "O padrão exige ao menos um passo habilitado")
    await _audit(db, c, user, "escalation_step", before, None)
    await _commit(db)


# ---------- calendários e feriados (compartilhados entre contratos) ----------


@router.get("/calendars")
async def list_calendars(
    _: User = Depends(require_operator), db: AsyncSession = Depends(get_db)
):
    cals = (await db.execute(select(SlaCalendar).order_by(SlaCalendar.id))).scalars()
    out = []
    for c in cals:
        hours = (
            await db.execute(
                select(SlaCalendarHours)
                .where(SlaCalendarHours.calendar_id == c.id)
                .order_by(SlaCalendarHours.weekday, SlaCalendarHours.start_time)
            )
        ).scalars()
        hols = (
            await db.execute(
                select(SlaHoliday)
                .where(SlaHoliday.calendar_id == c.id)
                .order_by(SlaHoliday.holiday_date)
            )
        ).scalars()
        out.append(
            {
                **_row(c),
                "hours": [_row(h) for h in hours],
                "holidays": [_row(h) for h in hols],
            }
        )
    return out


async def _in_use(db: AsyncSession, calendar_id: int) -> bool:
    for model in (Contract, SlaPolicy):
        if await db.scalar(
            select(func.count())
            .select_from(model)
            .where(model.calendar_id == calendar_id)
        ):
            return True
    return False


async def _audit_calendar(
    db: AsyncSession, calendar_id: int, user: User, entity: str, before, after
) -> None:
    """Calendário é compartilhado: registra em cada contrato ATIVO que o referencia."""
    ids = set(
        (
            await db.execute(
                select(Contract.id).where(
                    Contract.status == "active", Contract.calendar_id == calendar_id
                )
            )
        ).scalars()
    ) | set(
        (
            await db.execute(
                select(SlaPolicy.contract_id)
                .join(Contract, Contract.id == SlaPolicy.contract_id)
                .where(
                    SlaPolicy.calendar_id == calendar_id, Contract.status == "active"
                )
            )
        ).scalars()
    )
    logger.info(
        "sla_calendar_change",
        extra={
            "calendar_id": calendar_id,
            "user_id": user.id,
            "entity": entity,
            "before": before,
            "after": after,
        },
    )
    for cid in sorted(ids):
        db.add(
            ContractChange(
                contract_id=cid,
                changed_by_user_id=user.id,
                entity=entity,
                before=before,
                after=after,
            )
        )


@router.post("/calendars", status_code=201)
async def create_calendar(
    body: CalendarIn,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cal = SlaCalendar(**body.model_dump())
    db.add(cal)
    await _commit(db)
    return _row(cal)


@router.put("/calendars/{calendar_id}")
async def update_calendar(
    calendar_id: int,
    body: CalendarIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cal = await _get(db, SlaCalendar, calendar_id, "Calendário")
    before = _row(cal)
    for k, v in body.model_dump().items():
        setattr(cal, k, v)
    await db.flush()
    await _audit_calendar(db, cal.id, user, "calendar", before, _row(cal))
    await _commit(db)
    return _row(cal)


@router.delete("/calendars/{calendar_id}", status_code=204)
async def delete_calendar(
    calendar_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cal = await _get(db, SlaCalendar, calendar_id, "Calendário")
    if await _in_use(db, calendar_id):
        raise HTTPException(409, "Calendário em uso por contrato ou política")
    await db.delete(cal)
    await _commit(db)


@router.put("/calendars/{calendar_id}/hours")
async def replace_hours(
    calendar_id: int,
    body: list[HoursIn],
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Substitui todos os intervalos do calendário (vários por dia permitidos)."""
    await _get(db, SlaCalendar, calendar_id, "Calendário")
    old = (
        (
            await db.execute(
                select(SlaCalendarHours).where(
                    SlaCalendarHours.calendar_id == calendar_id
                )
            )
        )
        .scalars()
        .all()
    )
    before = [
        {
            "weekday": h.weekday,
            "start": h.start_time.isoformat(),
            "end": h.end_time.isoformat(),
        }
        for h in old
    ]
    await db.execute(
        delete(SlaCalendarHours).where(SlaCalendarHours.calendar_id == calendar_id)
    )
    db.add_all(
        SlaCalendarHours(calendar_id=calendar_id, **h.model_dump()) for h in body
    )
    after = [
        {
            "weekday": h.weekday,
            "start": h.start_time.isoformat(),
            "end": h.end_time.isoformat(),
        }
        for h in body
    ]
    await _audit_calendar(
        db, calendar_id, user, "calendar_hours", {"hours": before}, {"hours": after}
    )
    await _commit(db)
    return after


@router.put("/calendars/{calendar_id}/holidays/{holiday_date}")
async def upsert_holiday(
    calendar_id: int,
    holiday_date: date,
    body: HolidayIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if body.holiday_date != holiday_date:
        raise HTTPException(422, "holiday_date do corpo difere da URL")
    await _get(db, SlaCalendar, calendar_id, "Calendário")
    h = (
        await db.execute(
            select(SlaHoliday).where(
                SlaHoliday.calendar_id == calendar_id,
                SlaHoliday.holiday_date == holiday_date,
            )
        )
    ).scalar_one_or_none()
    before = _row(h) if h else None
    if h is None:
        h = SlaHoliday(calendar_id=calendar_id, holiday_date=holiday_date)
        db.add(h)
    h.name = body.name
    await db.flush()
    await _audit_calendar(db, calendar_id, user, "holiday", before, _row(h))
    await _commit(db)
    return _row(h)


@router.delete("/calendars/{calendar_id}/holidays/{holiday_date}", status_code=204)
async def delete_holiday(
    calendar_id: int,
    holiday_date: date,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    h = (
        await db.execute(
            select(SlaHoliday).where(
                SlaHoliday.calendar_id == calendar_id,
                SlaHoliday.holiday_date == holiday_date,
            )
        )
    ).scalar_one_or_none()
    if h is None:
        raise HTTPException(404, "Feriado não encontrado")
    before = _row(h)
    await db.delete(h)
    await db.flush()
    await _audit_calendar(db, calendar_id, user, "holiday", before, None)
    await _commit(db)
