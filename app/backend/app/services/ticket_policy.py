"""Política de chamado: o que exige ação, o que é causa, site do host e chave de dedup."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Literal

from sqlalchemy import select

from app.models import TicketRule

logger = logging.getLogger(__name__)

TICKET_DEFAULTS = {
    "ticket_grace_minutes": 15,
    "ticket_reopen_hours": 24,
    "ticket_symptom_lead_minutes": 2,
    "ticket_cross_link_minutes": 30,
}


@dataclass(frozen=True)
class Rules:
    action: list[re.Pattern] = field(default_factory=list)
    noise: list[re.Pattern] = field(default_factory=list)
    cause: list[re.Pattern] = field(default_factory=list)


async def load_rules(session) -> Rules:
    rules = Rules()
    rows = await session.execute(
        select(TicketRule.kind, TicketRule.pattern).where(TicketRule.enabled)
    )
    for kind, pattern in rows:
        try:
            getattr(rules, kind).append(re.compile(pattern, re.I))
        except (re.error, AttributeError):
            logger.warning("Regra de chamado inválida ignorada: %s", kind)
    return rules


def _hit(patterns: list[re.Pattern], title: str) -> bool:
    return any(p.search(title) for p in patterns)


def classify(title: str, severity: int, rules: Rules) -> Literal["action", "panel"]:
    """Severidade 4-5 sempre exige ação; senão ruído vence a lista de ação."""
    if severity >= 4:
        return "action"
    if _hit(rules.noise, title):
        return "panel"
    return "action" if _hit(rules.action, title) else "panel"


def is_cause(title: str, rules: Rules) -> bool:
    return _hit(rules.cause, title)


_SITE = re.compile(r"^(\[[^\]]+\]\s*\[[^\]]+\])")


def site_from_hostgroups(groups: list[str]) -> str | None:
    """`[ Cliente ] [ Site ]` do primeiro grupo com dois níveis ou mais."""
    for name in groups:
        match = _SITE.match(name.strip())
        if match:
            return re.sub(r"\]\s*\[", "] [", match.group(1))
    return None


def dedup_key(entity_id: int, host_id: str, trigger_id: str) -> str:
    return sha256(f"{entity_id}:{host_id}:{trigger_id}".encode()).hexdigest()
