import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, StringConstraints
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_admin, require_operator
from app.database import get_db
from app.models.models import Customer, CustomerAlias
from app.models.users import User
from app.services.customers import norm_alias

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customers", tags=["customers"])

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CustomerIn(BaseModel):
    key: NonBlank
    display_name: NonBlank
    glpi_entity_id: int | None = None
    active: bool = True
    aliases: list[NonBlank] = []


class CustomerPatch(BaseModel):
    display_name: NonBlank | None = None
    glpi_entity_id: int | None = None
    active: bool | None = None


class AliasIn(BaseModel):
    alias: NonBlank


def _fields(c: Customer) -> dict:
    return {
        "display_name": c.display_name,
        "glpi_entity_id": c.glpi_entity_id,
        "active": c.active,
    }


async def _out(session: AsyncSession, c: Customer) -> dict:
    aliases = (
        (
            await session.execute(
                select(CustomerAlias.alias_norm)
                .where(CustomerAlias.customer_id == c.id)
                .order_by(CustomerAlias.alias_norm)
            )
        )
        .scalars()
        .all()
    )
    return {"id": c.id, "key": c.key, **_fields(c), "aliases": list(aliases)}


async def _get(session: AsyncSession, customer_id: int) -> Customer:
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return customer


def _touch(c: Customer, user: User) -> None:
    c.updated_at = datetime.now(timezone.utc)
    c.updated_by_user_id = user.id


@router.get("")
async def list_customers(
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_operator),
):
    rows = (await session.execute(select(Customer).order_by(Customer.id))).scalars()
    return [await _out(session, c) for c in rows.all()]


@router.post("", status_code=201)
async def create_customer(
    body: CustomerIn,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    customer = Customer(
        key=body.key,
        display_name=body.display_name,
        glpi_entity_id=body.glpi_entity_id,
        active=body.active,
        updated_by_user_id=user.id,
    )
    try:
        session.add(customer)
        await session.flush()
        for alias in {norm_alias(a) for a in [body.display_name, *body.aliases]}:
            session.add(CustomerAlias(alias_norm=alias, customer_id=customer.id))
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Chave ou apelido já cadastrado")
    await session.commit()
    logger.info(
        "customer_created id=%s by=%s after=%s", customer.id, user.id, _fields(customer)
    )
    return await _out(session, customer)


@router.put("/{customer_id}")
async def update_customer(
    customer_id: int,
    body: CustomerPatch,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    customer = await _get(session, customer_id)
    before = _fields(customer)
    for name in body.model_fields_set:
        value = getattr(body, name)
        if value is None and name != "glpi_entity_id":
            raise HTTPException(status_code=422, detail=f"{name} não pode ser nulo")
        setattr(customer, name, value)
    _touch(customer, user)
    await session.commit()
    logger.info(
        "customer_updated id=%s by=%s before=%s after=%s",
        customer.id,
        user.id,
        before,
        _fields(customer),
    )
    return await _out(session, customer)


@router.post("/{customer_id}/aliases", status_code=201)
async def add_alias(
    customer_id: int,
    body: AliasIn,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    customer = await _get(session, customer_id)
    session.add(
        CustomerAlias(alias_norm=norm_alias(body.alias), customer_id=customer.id)
    )
    _touch(customer, user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Apelido já cadastrado")
    logger.info(
        "customer_alias_added id=%s by=%s alias=%s",
        customer.id,
        user.id,
        norm_alias(body.alias),
    )
    return await _out(session, customer)


@router.delete("/{customer_id}/aliases")
async def remove_alias(
    customer_id: int,
    alias: Annotated[str, Query(min_length=1)],
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    customer = await _get(session, customer_id)
    alias_norm = norm_alias(alias)
    result = await session.execute(
        delete(CustomerAlias).where(
            CustomerAlias.customer_id == customer.id,
            CustomerAlias.alias_norm == alias_norm,
        )
    )
    if not result.rowcount:  # type: ignore[attr-defined]
        await session.rollback()
        raise HTTPException(status_code=404, detail="Apelido não encontrado")
    _touch(customer, user)
    await session.commit()
    logger.info(
        "customer_alias_removed id=%s by=%s alias=%s", customer.id, user.id, alias_norm
    )
    return await _out(session, customer)
