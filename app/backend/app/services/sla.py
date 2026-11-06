"""Contratos, políticas de SLA, calendários e escalonamento: leitura e contas puras.

Nenhum valor de prazo mora aqui: tudo vem das tabelas editáveis (ver
docs/specs/contratos-sla-editaveis.md). Resolução: contrato ATIVO e vigente do tenant;
senão o contrato padrão interno (NÃO contratual). Contrato sem política habilitada para
a classe do incidente cai no padrão e registra WARNING (nunca herda em silêncio).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import (
    Contract,
    EscalationStep,
    SlaCalendar,
    SlaCalendarHours,
    SlaHoliday,
    SlaPolicy,
    UserRole,
)

logger = logging.getLogger("nessops.sla")
_HORIZON_DAYS = 800  # guarda contra calendário sem dia útil


@dataclass(frozen=True)
class CalendarCfg:
    timezone: str
    is_24x7: bool
    hours: dict[int, tuple[tuple[time, time], ...]]
    holidays: frozenset[date]


@dataclass(frozen=True)
class PolicyCfg:
    contract_id: int
    key: str
    min_severity: int | None
    severity: int | None
    has_tenant: bool | None
    ack: timedelta
    calendar: CalendarCfg


@dataclass(frozen=True)
class ContractCfg:
    id: int
    tenant_id: str | None
    is_default: bool
    contractual: bool
    starts_on: date | None
    ends_on: date | None
    timezone: str
    policies: tuple[PolicyCfg, ...]
    roles: tuple[UserRole, ...]


@dataclass(frozen=True)
class SlaConfig:
    contracts: tuple[ContractCfg, ...] = ()

    @property
    def default(self) -> ContractCfg | None:
        return next((c for c in self.contracts if c.is_default), None)

    def severity_floor(self, now: datetime) -> int | None:
        """Menor severidade coberta por política habilitada; None = nenhuma política."""
        floors = [
            _floor(p)
            for c in self.contracts
            if c.is_default or in_force(c, now)
            for p in c.policies
        ]
        return min(floors) if floors else None


def _floor(p: PolicyCfg) -> int:
    if p.min_severity is not None:
        return p.min_severity
    return p.severity if p.severity is not None else 0


def add_calendar_time(
    start: datetime, delta: timedelta, calendar: CalendarCfg
) -> datetime:
    """Soma `delta` de tempo útil do calendário (fuso, intervalos, feriados). Retorna UTC."""
    if calendar.is_24x7:
        return start.astimezone(timezone.utc) + delta
    tz = ZoneInfo(calendar.timezone)
    cur = start.astimezone(timezone.utc)
    day = cur.astimezone(tz).date()
    for _ in range(_HORIZON_DAYS):
        if day not in calendar.holidays:
            for s, e in sorted(calendar.hours.get(day.weekday(), ())):
                s_utc = datetime.combine(day, s, tz).astimezone(timezone.utc)
                e_utc = datetime.combine(day, e, tz).astimezone(timezone.utc)
                if cur >= e_utc:
                    continue
                begin = max(cur, s_utc)
                if delta <= e_utc - begin:
                    return begin + delta
                delta -= e_utc - begin
                cur = e_utc
        day += timedelta(days=1)
    raise ValueError("calendário sem tempo útil dentro do horizonte")


def in_force(c: ContractCfg, now: datetime) -> bool:
    today = now.astimezone(ZoneInfo(c.timezone)).date()
    return (c.starts_on is None or c.starts_on <= today) and (
        c.ends_on is None or today <= c.ends_on
    )


def _match(p: PolicyCfg, severity: int, has_tenant: bool) -> bool:
    return (
        (p.has_tenant is None or p.has_tenant == has_tenant)
        and (p.severity is None or p.severity == severity)
        and (p.min_severity is None or severity >= p.min_severity)
    )


def _pick(c: ContractCfg, severity: int, has_tenant: bool) -> PolicyCfg | None:
    hits = [p for p in c.policies if _match(p, severity, has_tenant)]
    # severidade exata é mais específica que piso
    return min(hits, key=lambda p: p.severity is None, default=None)


def resolve(
    cfg: SlaConfig, tenant: str, severity: int, now: datetime
) -> tuple[ContractCfg, PolicyCfg] | None:
    """(contrato, política) do incidente; None = sem aviso (abaixo do piso/sem política)."""
    default = cfg.default
    own = next(
        (
            c
            for c in cfg.contracts
            if tenant
            and not c.is_default
            and c.tenant_id == tenant
            and in_force(c, now)
        ),
        None,
    )
    if own is not None:
        hit = _pick(own, severity, True)
        if hit is not None:
            return own, hit
        logger.warning(
            "Contrato %s sem política habilitada para severidade %s; usando o padrão",
            own.id,
            severity,
        )
    if default is None:
        return None
    hit = _pick(default, severity, bool(tenant))
    return (default, hit) if hit else None


def roles_for(cfg: SlaConfig, contract: ContractCfg) -> tuple[UserRole, ...]:
    """Passos do contrato; sem nenhum habilitado, os do padrão."""
    return contract.roles or (cfg.default.roles if cfg.default else ())


async def load_config(session) -> SlaConfig:
    """Lê contratos ativos + padrão. Uma leitura por ciclo, sem cache entre ciclos."""
    contracts = (
        (
            await session.execute(
                select(Contract).where(
                    (Contract.status == "active") | Contract.is_default
                )
            )
        )
        .scalars()
        .all()
    )
    cals = {c.id: c for c in (await session.execute(select(SlaCalendar))).scalars()}
    hours: dict[int, dict[int, list[tuple[time, time]]]] = {}
    for h in (await session.execute(select(SlaCalendarHours))).scalars():
        hours.setdefault(h.calendar_id, {}).setdefault(h.weekday, []).append(
            (h.start_time, h.end_time)
        )
    holidays: dict[int, set[date]] = {}
    for h in (await session.execute(select(SlaHoliday))).scalars():
        holidays.setdefault(h.calendar_id, set()).add(h.holiday_date)

    def cal_cfg(cid: int | None) -> CalendarCfg | None:
        c = cals.get(cid) if cid else None
        if c is None:
            return None
        h = {d: tuple(v) for d, v in hours.get(c.id, {}).items()}
        return CalendarCfg(c.timezone, c.is_24x7, h, frozenset(holidays.get(c.id, ())))

    pols = (
        (await session.execute(select(SlaPolicy).where(SlaPolicy.enabled.is_(True))))
        .scalars()
        .all()
    )
    steps = (
        (
            await session.execute(
                select(EscalationStep)
                .where(EscalationStep.enabled.is_(True))
                .order_by(EscalationStep.position)
            )
        )
        .scalars()
        .all()
    )
    out = []
    for c in contracts:
        base = cal_cfg(c.calendar_id)
        if base is None:
            logger.warning("Contrato %s sem calendário; ignorado", c.id)
            continue
        plist = []
        for p in pols:
            if p.contract_id != c.id:
                continue
            cal = cal_cfg(p.calendar_id) or base
            if not cal.is_24x7 and not cal.hours:
                logger.warning("Política %s com calendário sem horário; ignorada", p.id)
                continue
            plist.append(
                PolicyCfg(
                    c.id,
                    p.key,
                    p.min_severity,
                    p.severity,
                    p.has_tenant,
                    timedelta(minutes=p.ack_minutes),
                    cal,
                )
            )
        roles = []
        for s in steps:
            if s.contract_id == c.id:
                try:
                    roles.append(UserRole(s.role))
                except ValueError:
                    logger.warning("Passo %s com papel inválido; ignorado", s.id)
        out.append(
            ContractCfg(
                c.id,
                (c.tenant_id or "").lower() or None,
                c.is_default,
                c.contractual,
                c.starts_on,
                c.ends_on,
                base.timezone,
                tuple(plist),
                tuple(roles),
            )
        )
    return SlaConfig(tuple(out))


def modality_divergences(contracts, mappings) -> list[dict]:
    """Contrato ativo x `tenant_mappings.modality` (somente leitura, sem escrita).

    `contracts`: (tenant_id, modality); `mappings`: (internal_customer_id, modality).
    Divergência = contrato ativo com modalidade e algum mapeamento do tenant diferente
    (inclusive mapeamento ainda sem modalidade).
    """
    cm = {t.lower(): m for t, m in contracts if t and m}
    return [
        {"tenant_id": t, "contract_modality": cm[t], "mapping_modality": m}
        for t, m in sorted(
            {((t or "").lower(), m) for t, m in mappings},
            key=lambda x: (x[0], x[1] or ""),
        )
        if t in cm and m != cm[t]
    ]
