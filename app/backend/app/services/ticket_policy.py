"""Política de chamado: o que exige ação, o que é causa, site do host e chave de dedup."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Literal

import regex
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
    action: list[regex.Pattern] = field(default_factory=list)
    noise: list[regex.Pattern] = field(default_factory=list)
    cause: list[regex.Pattern] = field(default_factory=list)


async def load_rules(session) -> Rules:
    rules = Rules()
    rows = await session.execute(
        select(TicketRule.kind, TicketRule.pattern).where(TicketRule.enabled)
    )
    for kind, pattern in rows:
        try:
            getattr(rules, kind).append(regex.compile(pattern, regex.I))
        except (regex.error, AttributeError):
            logger.warning("Regra de chamado inválida ignorada: %s", kind)
    return rules


MATCH_TIMEOUT = 0.02  # segundos por padrão; o decisor roda a cada 60 s


def _hit(patterns: list[regex.Pattern], title: str, fail_open: bool = False) -> bool:
    """`regex` aceita timeout; o `re` da stdlib não, e uma regra patológica pararia o decisor.

    Estouro no ruído conta como "não casou" (nunca suprime chamado); nas regras de ação,
    `fail_open` conta como "casou", para o chamado sair mesmo assim. O worker não trava.
    """
    for pattern in patterns:
        try:
            if pattern.search(title, timeout=MATCH_TIMEOUT):
                return True
        except TimeoutError:
            logger.warning("Regra de chamado estourou o tempo: %s", pattern.pattern)
            if fail_open:
                return True
    return False


def classify(title: str, severity: int, rules: Rules) -> Literal["action", "panel"]:
    """Severidade 4-5 sempre exige ação; senão ruído vence a lista de ação."""
    if severity >= 4:
        return "action"
    if _hit(rules.noise, title):
        return "panel"
    return "action" if _hit(rules.action, title, fail_open=True) else "panel"


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
