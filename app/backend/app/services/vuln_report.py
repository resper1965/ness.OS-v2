"""Resumo mensal de vulnerabilidades por e-mail (disparado por infra/scripts/vuln-carga.sh --email)."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.integrations.email import ResendEmailClient
from app.models.models import Vulnerability

SEVS = (
    ("Critical", "Crítica"),
    ("High", "Alta"),
    ("Medium", "Média"),
    ("Low", "Baixa"),
)


def body(rows: list[tuple[str, str, int]], machines: dict[str, int], link: str) -> str:
    """Texto do e-mail: uma linha por cliente com máquinas e contagem por severidade."""
    by: dict[str, dict[str, int]] = {}
    for customer, sev, n in rows:
        by.setdefault(customer, {})[sev] = n
    lines = ["Vulnerabilidades por cliente (coleta mensal):", ""]
    for c in sorted(by):
        sev = " · ".join(
            f"{label} {by[c].get(k, 0):,}".replace(",", ".") for k, label in SEVS
        )
        lines.append(f"{c.upper()}: {machines.get(c, 0)} máquinas · {sev}")
    lines += ["", f"Detalhe e planilha (botão Exportar planilha): {link}"]
    return "\n".join(lines)


async def send(to: str) -> str:
    v = Vulnerability
    async with SessionLocal() as db:
        rows = (
            (
                await db.execute(
                    select(v.customer_id, v.severity, func.count()).group_by(
                        v.customer_id, v.severity
                    )
                )
            )
            .tuples()
            .all()
        )
        machines = dict(
            (
                await db.execute(
                    select(v.customer_id, func.count(v.agent.distinct())).group_by(
                        v.customer_id
                    )
                )
            )
            .tuples()
            .all()
        )
    if not rows:
        raise SystemExit("sem vulnerabilidades carregadas; nada enviado")
    month = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%m/%Y")
    link = f"{get_settings().dashboard_base_url}/?view=vulns"
    sent = await ResendEmailClient.from_settings().send(
        to=[to],
        subject=f"ness.OS · vulnerabilidades {month}",
        text=body(list(rows), machines, link),
        idempotency_key=f"vuln-report-{month}-{to}",
    )
    return sent.email_id


if __name__ == "__main__":
    print(asyncio.run(send(sys.argv[1])))
