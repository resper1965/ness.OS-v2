"""P3: aviso de incidente por dois canais independentes (e-mail e Web Push) com escalonamento.

Aceite do provedor (`provider_result`) nunca é leitura: só `acknowledged_at` conta.
Conteúdo mínimo: caso, severidade e ação esperada; nada do cliente.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.dependencies import NOC_ROLES
from app.database import SessionLocal
from app.integrations.email import ResendEmailClient
from app.integrations.webpush import send_web_push
from app.models import Incident, Notification, PushSubscription, User, UserRole

logger = logging.getLogger("nessops.notifications")

# ponytail: Brasil sem horário de verão desde 2019, offset fixo evita depender de tzdata;
# upgrade path: zoneinfo + calendário de feriados quando o contrato exigir.
_BR = timezone(timedelta(hours=-3))
_OPEN, _CLOSE = time(8), time(18)
_SOURCE_WINDOW_DAYS = 7

# Janelas de resposta (soc-attendance-policy.md / p2-proposta-valores.md, aceitas em 04/11).
# (prazo, conta só em horário comercial). "1 dia útil" = 10 h comerciais.
_WINDOWS = {
    "critical": (timedelta(minutes=15), False),  # nível >= 12
    "elevated": (timedelta(hours=1), False),  # nível <= 6 com score >= 75
    "standard": (timedelta(hours=4), True),  # 7-11 e demais
    "no_client": (timedelta(hours=10), True),  # sem cliente: 1 dia útil
}
# Papéis na ordem de escalonamento (o responsável designado vai antes).
# ponytail: não existe escala de plantão no sistema; ordem fixa por papel, sem plantão
# próprio. Upgrade path: ler a escala existente quando houver fonte (GLPI/n.360).
ESCALATION_ROLES = (UserRole.soc, UserRole.noc, UserRole.operator, UserRole.admin)


def severity_window(severity: int, has_tenant: bool) -> str | None:
    """Classe de janela do incidente; None = abaixo do piso de aviso.

    ponytail: o Incident traz severidade Zabbix 0-5, não nível Wazuh/score; mapa
    5 -> critical, 4 -> elevated, 3 -> standard. Ricardo confirma o mapa.
    """
    if severity < 3:
        return None
    if not has_tenant:
        return "no_client"
    return {5: "critical", 4: "elevated"}.get(severity, "standard")


def _add_business(start: datetime, delta: timedelta) -> datetime:
    cur = start.astimezone(_BR)

    def opening(d: datetime) -> datetime:
        d = d.replace(hour=_OPEN.hour, minute=0, second=0, microsecond=0)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d

    if cur.weekday() >= 5 or cur.time() >= _CLOSE:
        cur = opening(cur + timedelta(days=1))
    elif cur.time() < _OPEN:
        cur = opening(cur)
    while True:
        avail = cur.replace(hour=_CLOSE.hour, minute=0, second=0, microsecond=0) - cur
        if delta <= avail:
            return cur + delta
        delta -= avail
        cur = opening(cur + timedelta(days=1))


def response_deadline(window: str, start: datetime) -> datetime:
    delta, business = _WINDOWS[window]
    return _add_business(start, delta) if business else start + delta


def next_escalation(
    *,
    window: str,
    step_at: datetime,
    step: int,
    total: int,
    acknowledged: bool,
    now: datetime,
) -> int | None:
    """Próximo degrau (índice de destinatário) ou None. Função pura.

    Escala só sem reconhecimento, com janela vencida e destinatário restante.
    """
    if acknowledged or step + 1 >= total:
        return None
    return step + 1 if now >= response_deadline(window, step_at) else None


def _message(inc: Incident) -> tuple[str, str]:
    subject = f"[ness.OS] Caso #{inc.id} - severidade {inc.severity}/5"
    return subject, f"{subject}\nAção esperada: reconhecer o caso no ness.OS."


async def _send_email(user: User, inc: Incident, step: int) -> tuple[bool, str]:
    subject, text = _message(inc)
    try:
        sent = await ResendEmailClient.from_settings().send(
            to=[user.email],
            subject=subject,
            text=text,
            idempotency_key=f"notif-{inc.id}-{user.id}-{step}",
        )
        return True, f"accepted:{sent.email_id}"
    except Exception as exc:  # noqa: BLE001 - canal falho não pode derrubar o outro
        logger.warning("E-mail do caso %s falhou: %s", inc.id, type(exc).__name__)
        return False, f"error:{type(exc).__name__}"


async def _send_push(session, user: User, inc: Incident, step: int) -> tuple[bool, str]:
    subject, text = _message(inc)
    try:
        subs = (
            (
                await session.execute(
                    select(PushSubscription).where(PushSubscription.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        if not subs:
            return False, "error:no_subscription"
        payload = {
            "title": subject,
            "body": text.splitlines()[-1],
            "incident_id": str(inc.id),
            "severity": str(inc.severity),
        }
        oks = await asyncio.gather(*(send_web_push(s, payload) for s in subs))
        return any(oks), f"{sum(oks)}/{len(subs)} accepted"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Push do caso %s falhou: %s", inc.id, type(exc).__name__)
        return False, f"error:{type(exc).__name__}"


def _tenant(inc: Incident) -> str:
    return ((inc.tags or {}).get("ninf_customer_name") or "").lower()


async def _recipients(session, inc: Incident) -> list[User]:
    """Resolvidos no backend: papel + tenant do incidente; global só soc/noc/admin."""
    tenant = _tenant(inc)
    stmt = select(User).where(User.is_active.is_(True), User.role.in_(ESCALATION_ROLES))
    users = (await session.execute(stmt)).scalars().all()
    eligible = [
        u
        for u in users
        if (u.role in NOC_ROLES) or (tenant and (u.tenant_id or "").lower() == tenant)
    ]
    rank = {r: i for i, r in enumerate(ESCALATION_ROLES)}
    return sorted(
        eligible,
        key=lambda u: (u.id != inc.assigned_user_id, rank[u.role], u.id),
    )


async def _notify(session, inc: Incident, user: User, step: int, now: datetime) -> None:
    """Dois canais, independentes; o slot único torna a repetição idempotente."""
    for channel in ("email", "push"):
        claimed = (
            await session.execute(
                pg_insert(Notification)
                .values(
                    incident_id=inc.id,
                    user_id=user.id,
                    channel=channel,
                    step=step,
                    created_at=now,
                )
                .on_conflict_do_nothing(constraint="uq_notifications_slot")
                .returning(Notification.id)
            )
        ).scalar_one_or_none()
        await session.commit()
        if claimed is None:
            continue
        if channel == "email":
            ok, detail = await _send_email(user, inc, step)
        else:
            ok, detail = await _send_push(session, user, inc, step)
        await session.execute(
            update(Notification)
            .where(Notification.id == claimed)
            .values(provider_result=detail, sent_at=now if ok else None)
        )
        await session.commit()


async def sweep(now: datetime | None = None) -> dict[str, int]:
    """Avisa incidentes novos, escala os sem reconhecimento e carimba resolução."""
    now = now or datetime.now(timezone.utc)
    stats = {"notified": 0, "escalated": 0}
    async with SessionLocal() as session:
        await session.execute(
            update(Notification)
            .where(
                Notification.resolved_at.is_(None),
                Notification.incident_id.in_(
                    select(Incident.id).where(
                        Incident.status.in_(("resolved", "closed"))
                    )
                ),
            )
            .values(resolved_at=now)
        )
        await session.commit()
        incidents = (
            (
                await session.execute(
                    select(Incident).where(
                        Incident.status == "open",
                        Incident.severity >= 3,
                        Incident.first_seen
                        >= now - timedelta(days=_SOURCE_WINDOW_DAYS),
                    )
                )
            )
            .scalars()
            .all()
        )
        for inc in incidents:
            rows = (
                (
                    await session.execute(
                        select(Notification).where(Notification.incident_id == inc.id)
                    )
                )
                .scalars()
                .all()
            )
            people = await _recipients(session, inc)
            window = severity_window(inc.severity, bool(_tenant(inc)))
            if not people or window is None:
                continue
            if not rows:
                await _notify(session, inc, people[0], 0, now)
                stats["notified"] += 1
                continue
            done = {r.user_id for r in rows}
            pending = [u for u in people if u.id not in done]
            step = max(r.step for r in rows)
            nxt = next_escalation(
                window=window,
                step_at=max(r.created_at for r in rows if r.step == step),
                step=step,
                total=step + 1 + len(pending),
                acknowledged=any(r.acknowledged_at for r in rows),
                now=now,
            )
            if nxt is not None and pending:
                await _notify(session, inc, pending[0], nxt, now)
                stats["escalated"] += 1
    return stats
