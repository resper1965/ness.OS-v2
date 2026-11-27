"""Resumo diário e semanal por cliente — enviado ao gestor (role=cliente, summary_recipient).

Puxa dados da tabela de incidentes, tickets e SLA; o HTML é mínimo (sem dependência).
Idempotente por `ClientSummary.key`; o Resend usa idempotency_key próprio.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select

from app.database import SessionLocal
from app.integrations.email import EmailDeliveryError, ResendEmailClient
from app.models import Customer, Incident, TeamMember, TicketLink
from app.models.users import ClientSummary, User, UserRole

logger = logging.getLogger("nessops.client_summary")

BRT = timezone(timedelta(hours=-3))


def _today_kinds(now: datetime) -> list[tuple[str, timedelta]]:
    """Retorna (kind, janela) para as 08:00 de hoje. Segunda-feira inclui a semanal."""
    today = now.astimezone(BRT).replace(hour=8, minute=0, second=0, microsecond=0)
    kinds: list[tuple[str, timedelta]] = [("daily", timedelta(hours=24))]
    if today.weekday() == 0:
        kinds.append(("weekly", timedelta(days=7)))
    return kinds


async def _summary(session, customer_id: int, since: datetime) -> dict:
    """Dados para um resumo HTML: tickets, incidentes e texto."""

    tickets = (
        await session.execute(
            select(
                TicketLink.state,
                func.count(TicketLink.entity_id),
            )
            .where(
                TicketLink.last_seen >= since,
                TicketLink.entity_id == customer_id,
            )
            .group_by(TicketLink.state)
        )
    ).all()

    incs = (
        await session.execute(
            select(
                func.count(Incident.id),
                func.count(Incident.id).filter(Incident.severity >= 4),
                func.count(Incident.id).filter(
                    Incident.tags["ninf_branch"].astext == "soc"
                ),
            ).where(
                Incident.first_seen >= since,
                func.coalesce(Incident.tags["ninf_customer_id"].astext.cast(int), 0)
                == customer_id,
            )
        )
    ).one()

    return {
        "total": incs[0] or 0,
        "criticos": incs[1] or 0,
        "soc": incs[2] or 0,
        "tickets_abertos": sum(c for s, c in tickets if s == "open"),
        "tickets_fechados": sum(
            c for s, c in tickets if s in ("closed", "auto_closed")
        ),
    }


def _render(label: str, data: dict, since_label: str) -> str:
    """HTML mínimo, sem CSS externo."""
    return f"""<h2>{label}</h2>
<p>Período: {since_label}</p>
<table>
<tr><td>Incidentes:</td><td>{data["total"]}</td></tr>
<tr><td>Críticos (sev ≥ 4):</td><td>{data["criticos"]}</td></tr>
<tr><td>SOC:</td><td>{data["soc"]}</td></tr>
<tr><td>Chamados abertos:</td><td>{data["tickets_abertos"] or 0}</td></tr>
<tr><td>Chamados fechados:</td><td>{data["tickets_fechados"] or 0}</td></tr>
</table>
"""


async def run_summaries(
    now: datetime | None = None, dry: bool = False
) -> dict[str, int]:
    """Roda os resumos de hoje (diário; semanal às segundas)."""

    now = now or datetime.now(timezone.utc)
    kinds = _today_kinds(now)
    if not kinds:
        return {"no_summaries_due": 0}

    async with SessionLocal() as s:
        # Clientes ativos que têm ao menos um gestor cadastrado
        rows = (
            await s.execute(
                select(Customer, User)
                .join(TeamMember, TeamMember.customer_id == Customer.id)
                .join(
                    User, and_(User.id == TeamMember.user_id, User.is_active.is_(True))
                )
                .where(
                    Customer.active.is_(True),
                    User.role == UserRole.cliente,
                )
                .distinct()
            )
        ).all()

        # Cada item: (to, subject, html, key, idemp_key)
        emails: list = []

        for cust, user in rows:
            for kind, window in kinds:
                key = f"{now.astimezone(BRT).strftime('%Y-%m-%d')}-{kind}-{cust.key}"
                idemp_key = f"summary-{key}-{user.id}"

                # Já enviado?
                exists = await s.scalar(
                    select(ClientSummary.id).where(
                        ClientSummary.customer_id == cust.id,
                        ClientSummary.key == key,
                    )
                )
                if exists:
                    continue

                since = now - window
                data = await _summary(s, cust.id, since)

                label = "Resumo diário" if kind == "daily" else "Resumo da semana"
                since_label = since.astimezone(BRT).strftime("%d/%m/%Y %H:%M")
                html = _render(f"{label} — {cust.display_name}", data, since_label)

                if not dry:
                    s.add(
                        ClientSummary(
                            customer_id=cust.id,
                            key=key,
                            kind=kind,
                            html=html,
                        )
                    )

                emails.append((user.email, f"{label} - ness.OS", html, key, idemp_key))

        if not dry:
            await s.commit()

    # Envio (fora da sessão, para o Resend não segurar conexão de banco)
    sent = 0
    if emails and not dry:
        client = ResendEmailClient.from_settings()
        for to, subject, html, _key, idemp_key in emails:
            try:
                await client.send(
                    to=[to],
                    subject=subject,
                    html=html,
                    idempotency_key=idemp_key,
                )
                sent += 1
            except EmailDeliveryError:
                logger.exception("Falha ao enviar resumo para %s", to)
    elif emails and dry:
        sent = len(emails)

    logger.info("client_summaries done: %d sent, %d skipped", sent, len(emails) - sent)
    return {"enviados": sent, "ignorados": len(emails) - sent}
