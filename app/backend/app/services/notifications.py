"""P3: aviso de incidente por dois canais independentes (e-mail e Web Push) com escalonamento.

Aceite do provedor (`provider_result`) nunca é leitura: só `acknowledged_at` conta.
Conteúdo mínimo: caso, severidade e ação esperada; nada do cliente.
Reenvio: o e-mail é deduplicado pelo Idempotency-Key; o push pode duplicar se o worker
morrer entre o envio e a gravação de `sent_at` (o provedor não tem idempotência).
"""

from __future__ import annotations

import asyncio
import logging
import time as _time
from collections.abc import Coroutine
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.dependencies import NOC_ROLES
from app.database import SessionLocal
from app.integrations.email import ResendEmailClient
from app.integrations.webpush import send_web_push
from app.models import (
    Incident,
    IncidentAction,
    Notification,
    PushSubscription,
    User,
)
from app.services.sla import (
    PolicyCfg,
    add_calendar_time,
    load_config,
    resolve,
    roles_for,
)

logger = logging.getLogger("nessops.notifications")

# Primeiro deploy não pode disparar rajada sobre incidentes antigos.
_SOURCE_WINDOW_HOURS = 24
_MAX_INCIDENTS_PER_SWEEP = 50
# Teto abaixo do task_time_limit (120 s): para e continua no ciclo seguinte.
_SWEEP_BUDGET_SECONDS = 90.0
_CHANNEL_TIMEOUT_SECONDS = 15.0
# Tentativa sem aceite do provedor volta a ser elegível após o lease (enquanto o caso
# estiver aberto e dentro da janela de 24 h); o aceite encerra o slot.
_LEASE = timedelta(minutes=5)
_MAX_ATTEMPTS = 5
_NO_SUBSCRIPTION = "error:no_subscription"  # não retenta: nada a reenviar

# Prazos, calendários, severidade mínima e ordem de escalonamento vêm do contrato do
# tenant (ou do padrão interno NÃO contratual): ver app/services/sla.py. Nada embutido aqui.
# ponytail: não existe escala de plantão no sistema; a ordem é por papel (passos do
# contrato). Upgrade path: ler a escala existente quando houver fonte (GLPI/n.360).


def response_deadline(policy: PolicyCfg, start: datetime) -> datetime:
    return add_calendar_time(start, policy.ack, policy.calendar)


def next_escalation(
    *,
    policy: PolicyCfg,
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
    return step + 1 if now >= response_deadline(policy, step_at) else None


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


async def _push_subscriptions(session, user: User) -> list[PushSubscription]:
    # Fora do wait_for: cancelar um SELECT deixaria a sessão compartilhada inválida.
    res = await session.execute(
        select(PushSubscription).where(PushSubscription.user_id == user.id)
    )
    return list(res.scalars().all())


async def _send_push(subs: list[PushSubscription], inc: Incident) -> tuple[bool, str]:
    """Só HTTP, sem sessão do chamador: pode ser cancelada pelo timeout com segurança."""
    subject, text = _message(inc)
    try:
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


async def _recipients(session, inc: Incident, roles) -> list[User]:
    """Resolvidos no backend: papel (passos do contrato) + tenant do incidente."""
    tenant = _tenant(inc)
    stmt = select(User).where(User.is_active.is_(True), User.role.in_(roles))
    users = (await session.execute(stmt)).scalars().all()
    eligible = [
        u
        for u in users
        if (u.role in NOC_ROLES) or (tenant and (u.tenant_id or "").lower() == tenant)
    ]
    rank = {r: i for i, r in enumerate(roles)}
    return sorted(
        eligible,
        key=lambda u: (u.id != inc.assigned_user_id, rank[u.role], u.id),
    )


async def _claim(session, inc: Incident, user: User, channel: str, step: int, now):
    """Reivindica o slot com lease. Id da tentativa, ou None se já entregue ou em lease.

    Um slot sem aceite do provedor (abandonado por morte do worker ou com erro) só é
    reivindicado de novo depois do lease; o aceite encerra o slot.
    """
    slot = dict(incident_id=inc.id, user_id=user.id, channel=channel, step=step)
    claimed = (
        await session.execute(
            pg_insert(Notification)
            .values(**slot, created_at=now, claimed_at=now, attempts=1)
            .on_conflict_do_nothing(constraint="uq_notifications_slot")
            .returning(Notification.id)
        )
    ).scalar_one_or_none()
    if claimed is None:
        claimed = (
            await session.execute(
                update(Notification)
                .where(
                    *(getattr(Notification, k) == v for k, v in slot.items()),
                    Notification.sent_at.is_(None),
                    Notification.claimed_at <= now - _LEASE,
                    Notification.attempts < _MAX_ATTEMPTS,
                    Notification.provider_result.is_distinct_from(_NO_SUBSCRIPTION),
                )
                .values(claimed_at=now, attempts=Notification.attempts + 1)
                .returning(Notification.id)
            )
        ).scalar_one_or_none()
    await session.commit()
    return claimed


async def _notify(session, inc: Incident, user: User, step: int, now: datetime) -> None:
    """Dois canais, independentes, cada um com timeout; falha ou lentidão de um não trava o outro."""
    for channel in ("email", "push"):
        claimed = await _claim(session, inc, user, channel, step, now)
        if claimed is None:
            continue
        try:
            send: Coroutine[Any, Any, tuple[bool, str]] | None
            if channel == "email":
                send = _send_email(user, inc, step)
            else:
                subs = await _push_subscriptions(session, user)
                send = _send_push(subs, inc) if subs else None
            if send is None:
                ok, detail = False, _NO_SUBSCRIPTION
            else:
                ok, detail = await asyncio.wait_for(send, _CHANNEL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            ok, detail = False, "error:timeout"
        except Exception as exc:  # noqa: BLE001 - um canal nunca derruba a varredura
            await session.rollback()
            ok, detail = False, f"error:{type(exc).__name__}"
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
    started = _time.monotonic()
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
        # Uma leitura por ciclo, sem cache: editar o contrato vale no ciclo seguinte.
        cfg = await load_config(session)
        floor = cfg.severity_floor(now)
        if floor is None:
            logger.warning("Nenhuma política de SLA habilitada; varredura não avisa")
            return stats
        # ponytail: os 50 mais novos por severidade; acima disso o excedente espera o
        # ciclo seguinte. Upgrade path: cursor/paginação se houver mais de 50 abertos.
        incidents = (
            (
                await session.execute(
                    select(Incident)
                    .where(
                        Incident.status == "open",
                        Incident.severity >= floor,
                        Incident.first_seen
                        >= now - timedelta(hours=_SOURCE_WINDOW_HOURS),
                    )
                    .order_by(Incident.severity.desc(), Incident.first_seen.desc())
                    .limit(_MAX_INCIDENTS_PER_SWEEP)
                )
            )
            .scalars()
            .all()
        )
        # Ack prévio (sem aviso ainda) fica só como IncidentAction; vale como reconhecido.
        pre_acked = set(
            (
                await session.execute(
                    select(IncidentAction.incident_id).where(
                        IncidentAction.action == "notification_ack",
                        IncidentAction.incident_id.in_([i.id for i in incidents]),
                    )
                )
            ).scalars()
        )
        for inc in incidents:
            if _time.monotonic() - started > _SWEEP_BUDGET_SECONDS:
                logger.warning(
                    "Varredura parou no teto de tempo; segue no próximo ciclo"
                )
                break
            if inc.id in pre_acked:
                continue
            rows = (
                (
                    await session.execute(
                        select(Notification).where(Notification.incident_id == inc.id)
                    )
                )
                .scalars()
                .all()
            )
            hit = resolve(cfg, _tenant(inc), inc.severity, now)
            if hit is None:
                continue
            contract, policy = hit
            people = await _recipients(session, inc, roles_for(cfg, contract))
            if not people:
                continue
            if not rows:
                await _notify(session, inc, people[0], 0, now)
                stats["notified"] += 1
                continue
            if any(r.acknowledged_at for r in rows):
                continue
            step = max(r.step for r in rows)
            current = [r for r in rows if r.step == step]
            # Repete a entrega do degrau atual onde o provedor não aceitou (lease em _claim).
            holder = next((u for u in people if u.id == current[0].user_id), None)
            if holder is not None:
                await _notify(session, inc, holder, step, now)
            # A janela conta do primeiro aceite do provedor, não da tentativa.
            accepted = [r.sent_at for r in current if r.sent_at]
            done = {r.user_id for r in rows}
            pending = [u for u in people if u.id not in done]
            # Esgotado = todo slot do degrau sem aceite e sem tentativas restantes.
            exhausted = not accepted and all(
                r.attempts >= _MAX_ATTEMPTS or r.provider_result == _NO_SUBSCRIPTION
                for r in current
            )
            if exhausted and holder is not None:
                logger.warning(
                    "Degrau %s do caso %s esgotado sem aceite; passando ao próximo",
                    step,
                    inc.id,
                )
            if not accepted and holder is not None and not exhausted:
                continue
            # Titular inativo/inelegível ou degrau esgotado sem aceite: degrau vazio,
            # passa ao próximo já.
            nxt = (
                step + 1
                if not accepted
                else next_escalation(
                    policy=policy,
                    step_at=min(accepted),
                    step=step,
                    total=step + 1 + len(pending),
                    acknowledged=False,
                    now=now,
                )
            )
            if nxt is not None and pending:
                await _notify(session, inc, pending[0], nxt, now)
                stats["escalated"] += 1
    return stats
