"""Cadastro único de pessoas e equipes (spec 2026-11-24). O GLPI é reconciliado a partir daqui."""

import logging
import secrets
from typing import Annotated, Literal

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, StringConstraints
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_admin
from app.database import get_db
from app.models import Customer, TeamMember, User, UserRole

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/people", tags=["people"])
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PersonIn(BaseModel):
    email: EmailStr
    full_name: NonBlank
    kind: Literal["ness", "externo"]
    customer_ids: list[int] = []
    is_oncall: bool = False


class PersonPatch(BaseModel):
    full_name: NonBlank | None = None
    customer_ids: list[int] | None = None
    is_oncall: bool | None = None
    is_active: bool | None = None


def _kick() -> None:
    """Reconcilia o GLPI sem prender a requisição; o ciclo do worker repara qualquer falha."""
    try:
        from app.workers.celery_app import celery_app

        celery_app.send_task("app.workers.tasks.sync_glpi_team")
    except Exception:  # noqa: BLE001
        logger.warning("sync_glpi_team não enfileirada; o ciclo de 15 min cobre")


async def _customers(db: AsyncSession, ids: list[int]) -> list[Customer]:
    ids = sorted(set(ids))
    rows = (
        (
            await db.execute(
                select(Customer).where(Customer.id.in_(ids), Customer.active.is_(True))
            )
        )
        .scalars()
        .all()
        if ids
        else []
    )
    if len(rows) != len(ids):
        raise HTTPException(422, "Cliente inexistente ou inativo")
    if any(c.glpi_entity_id is None for c in rows):
        raise HTTPException(422, "Cliente sem entidade GLPI não aceita equipe")
    return list(rows)


_TEAM_ROLES = {
    UserRole.noc,
    UserRole.soc,
    UserRole.operator,
    UserRole.admin,
    UserRole.platform_admin,
    UserRole.cliente,
}


def _check(external: bool, customers: list[Customer], oncall: bool) -> None:
    if external and len(customers) != 1:
        raise HTTPException(422, "Técnico externo precisa de exatamente 1 cliente")
    if external and oncall:
        raise HTTPException(422, "Técnico externo não entra no plantão")


async def _out(db: AsyncSession, u: User) -> dict:
    ids = (
        (
            await db.execute(
                select(TeamMember.customer_id).where(TeamMember.user_id == u.id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "kind": "externo" if u.role == UserRole.cliente else "ness",
        "role": u.role.value,
        "customer_ids": sorted(ids),
        "is_oncall": u.is_oncall,
        "is_active": u.is_active,
    }


@router.get("")
async def list_people(
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
):
    users = (await db.execute(select(User).order_by(User.email))).scalars().all()
    return [await _out(db, u) for u in users]


@router.get("/sync")
async def sync_status(_: User = Depends(require_admin)):
    """Simulação: o que o GLPI ainda não reflete. Lista vazia = em dia."""
    from app.services.glpi_team_sync import run_sync

    try:
        return {"diff": await run_sync(apply=False)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"GLPI indisponível: {type(exc).__name__}")


@router.post("", status_code=201)
async def create_person(
    body: PersonIn,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    external = body.kind == "externo"
    customers = await _customers(db, body.customer_ids)
    _check(external, customers, body.is_oncall)
    email = body.email.lower()
    taken = (
        await db.execute(
            select(User.id).where(
                func.lower(func.split_part(User.email, "@", 1))
                == email.split("@")[0].lower()
            )
        )
    ).first()
    if taken:
        raise HTTPException(409, "Já existe pessoa com o mesmo login antes do @")
    user = User(
        email=email,
        full_name=body.full_name,
        # Sem senha utilizável: o acesso é pelo SSO (identidade vinculada pelo admin).
        hashed_password=bcrypt.hashpw(
            secrets.token_urlsafe(32).encode(), bcrypt.gensalt()
        ).decode(),
        role=UserRole.cliente if external else UserRole.noc,
        tenant_id=customers[0].key if external else None,
        is_oncall=body.is_oncall,
    )
    try:
        db.add(user)
        await db.flush()
        db.add_all(TeamMember(customer_id=c.id, user_id=user.id) for c in customers)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "E-mail já cadastrado")
    logger.info("person_created id=%s kind=%s by=%s", user.id, body.kind, admin.id)
    _kick()
    return await _out(db, user)


@router.put("/{user_id}")
async def update_person(
    user_id: int,
    body: PersonPatch,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Pessoa não encontrada")
    if user.role == UserRole.platform_admin and admin.role != UserRole.platform_admin:
        raise HTTPException(403, "Só platform_admin altera platform_admin")
    external = user.role == UserRole.cliente
    current = (await _out(db, user))["customer_ids"]
    customers = await _customers(
        db, body.customer_ids if body.customer_ids is not None else current
    )
    oncall = user.is_oncall if body.is_oncall is None else body.is_oncall
    _check(external, customers, oncall)
    if (customers or oncall) and user.role not in _TEAM_ROLES:
        raise HTTPException(422, "Papel sem acesso operacional não entra em equipe")
    if body.full_name:
        user.full_name = body.full_name
    user.is_oncall = oncall
    if external:
        user.tenant_id = customers[0].key
    if body.is_active is False and user.id == admin.id:
        raise HTTPException(409, "Não é possível desativar a si mesmo")
    if body.is_active is not None and body.is_active != user.is_active:
        user.is_active = body.is_active
        user.session_epoch += 1
    await db.execute(delete(TeamMember).where(TeamMember.user_id == user.id))
    db.add_all(TeamMember(customer_id=c.id, user_id=user.id) for c in customers)
    await db.commit()
    logger.info("person_updated id=%s by=%s", user.id, admin.id)
    _kick()
    return await _out(db, user)


@router.delete("/{user_id}")
async def deactivate_person(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Pessoa não encontrada")
    if user.role == UserRole.platform_admin and admin.role != UserRole.platform_admin:
        raise HTTPException(403, "Só platform_admin altera platform_admin")
    if user.id == admin.id:
        raise HTTPException(409, "Não é possível desativar a si mesmo")
    user.is_active = False
    user.is_oncall = False
    user.session_epoch += 1
    await db.commit()
    logger.info("person_deactivated id=%s by=%s", user.id, admin.id)
    _kick()
    return await _out(db, user)
