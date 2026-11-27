"""Regras de chamado editáveis (ruído, ação, causa): leitura NOC, escrita só platform_admin.

O decisor lê a tabela a cada ciclo (60 s), então a mudança vale sem deploy.
"""

from __future__ import annotations

import logging
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_noc, require_platform_admin
from app.database import get_db
from app.models import TicketRule, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ticket-rules", tags=["ticket-rules"])

Pattern = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class RuleIn(BaseModel):
    kind: Literal["action", "noise", "cause"]
    pattern: Pattern
    note: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None
    ) = None


class RulePatch(BaseModel):
    enabled: bool


# ponytail: heurística, não prova; o re do Python não tem timeout. Pega o caso clássico
# (grupo com quantificador repetido por outro quantificador); upgrade path: o pacote `re2`.
_NESTED = re.compile(r"[+*}]\)[+*{]")


def _out(r: TicketRule) -> dict:
    return {
        "id": r.id,
        "kind": r.kind,
        "pattern": r.pattern,
        "note": r.note,
        "enabled": r.enabled,
    }


async def _get(db: AsyncSession, rule_id: int) -> TicketRule:
    row = await db.get(TicketRule, rule_id)
    if row is None:
        raise HTTPException(404, "Regra não encontrada")
    return row


def _log(op: str, user: User, rule: TicketRule) -> None:
    logger.info(
        "ticket_rule_change",
        extra={"op": op, "user_id": user.id, "rule_id": rule.id, "kind": rule.kind},
    )


@router.get("")
async def list_rules(
    user: User = Depends(require_noc), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    rows = await db.execute(select(TicketRule).order_by(TicketRule.kind, TicketRule.id))
    return [_out(r) for r in rows.scalars()]


@router.post("", status_code=201)
async def create_rule(
    body: RuleIn,
    user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        re.compile(body.pattern, re.I)
    except re.error as exc:
        raise HTTPException(422, f"Expressão inválida: {exc}") from exc
    if _NESTED.search(body.pattern):
        raise HTTPException(
            422, "Expressão com repetição aninhada (ex.: (a+)+) trava o decisor"
        )
    row = TicketRule(kind=body.kind, pattern=body.pattern, note=body.note or None)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Essa regra já existe") from exc
    _log("create", user, row)
    return _out(row)


@router.patch("/{rule_id}")
async def toggle_rule(
    rule_id: int,
    body: RulePatch,
    user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await _get(db, rule_id)
    row.enabled = body.enabled
    await db.commit()
    _log("toggle", user, row)
    return _out(row)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: int,
    user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    row = await _get(db, rule_id)
    await db.delete(row)
    await db.commit()
    _log("delete", user, row)
    return Response(status_code=204)
