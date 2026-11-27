"""Regras de chamado editáveis (ruído, ação, causa): leitura NOC, escrita só platform_admin.

O decisor lê a tabela a cada ciclo (60 s), então a mudança vale sem deploy.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

import regex
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


def _mask(pattern: str) -> str:
    """Troca escapes e conteúdo de classe de caracteres por `x`, mantendo as posições.

    Assim `(\\+)+` e `([+])+` repetem só um literal e não contam como repetição aninhada.
    """
    out = list(pattern)
    i = 0
    while i < len(pattern):
        if pattern[i] == "\\" and i + 1 < len(pattern):
            out[i] = out[i + 1] = "x"
            i += 2
        elif pattern[i] == "[":
            j = i + 1
            while j < len(pattern) and pattern[j] != "]":
                j += 2 if pattern[j] == "\\" else 1
            for k in range(i, min(j + 1, len(pattern))):
                out[k] = "x"
            i = j + 1
        else:
            i += 1
    return "".join(out)


def _unsafe(pattern: str) -> bool:
    """Grupo que já repete ou alterna, repetido de novo (`(a+)+`, `(a|aa)+`), trava o `re`.

    O `re` do Python não tem timeout e `_hit()` roda em todo incidente do decisor: uma
    expressão assim pararia a abertura de chamados de todos os clientes. Bloqueia na
    escrita com checagem estrutural; não é prova de linearidade, mas pega o caso real.
    ponytail: heurística; upgrade path: `re2` quando houver wheel na imagem.
    """
    masked = _mask(pattern)
    stack: list[int] = []
    for i, ch in enumerate(masked):
        if ch == "(":
            stack.append(i)
        elif ch == ")" and stack:
            body = masked[stack.pop() + 1 : i]
            if body.startswith("?P<"):  # grupo nomeado: o prefixo não é quantificador
                body = body.split(">", 1)[-1]
            elif body.startswith("?:"):
                body = body[2:]
            if masked[i + 1 : i + 2] in ("+", "*", "{") and any(
                c in body for c in "+*{|?"
            ):
                return True
    return False


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
        regex.compile(body.pattern, regex.I)
    except regex.error as exc:
        raise HTTPException(422, f"Expressão inválida: {exc}") from exc
    if _unsafe(body.pattern):
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
