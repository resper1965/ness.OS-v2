"""Contatos de aviso do cliente (dado pessoal).

Dado de plataforma, não de tenant: leitura só para papéis NOC globais (noc/soc/admin/
platform_admin; `operator` é escopado a tenant e `client`/`viewer` não leem); escrita
admin/platform_admin. Log e auditoria guardam só ids e nomes de campos, nunca e-mail
ou telefone. Nada consome os contatos ainda.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_admin, require_noc
from app.database import get_db
from app.models.models import Customer, CustomerContact
from app.models.users import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customers/{customer_id}/contacts", tags=["customers"])

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ContactIn(BaseModel):
    name: NonBlank
    email: EmailStr
    phone: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None
    ) = None
    role: NonBlank
    notify_severity_min: int = Field(ge=1, le=5)
    active: bool = True


class ContactPatch(BaseModel):
    name: NonBlank | None = None
    email: EmailStr | None = None
    phone: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None
    ) = None
    role: NonBlank | None = None
    notify_severity_min: int | None = Field(default=None, ge=1, le=5)
    active: bool | None = None


def _out(c: CustomerContact) -> dict:
    return {
        "id": c.id,
        "customer_id": c.customer_id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "role": c.role,
        "notify_severity_min": c.notify_severity_min,
        "active": c.active,
    }


async def _customer(session: AsyncSession, customer_id: int) -> None:
    if await session.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")


async def _contact(
    session: AsyncSession, customer_id: int, contact_id: int
) -> CustomerContact:
    await _customer(session, customer_id)
    contact = await session.get(CustomerContact, contact_id)
    if contact is None or contact.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    return contact


@router.get("")
async def list_contacts(
    customer_id: int,
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_noc),
):
    await _customer(session, customer_id)
    rows = await session.execute(
        select(CustomerContact)
        .where(CustomerContact.customer_id == customer_id)
        .order_by(CustomerContact.id)
    )
    return [_out(c) for c in rows.scalars()]


@router.post("", status_code=201)
async def create_contact(
    customer_id: int,
    body: ContactIn,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    await _customer(session, customer_id)
    contact = CustomerContact(customer_id=customer_id, **body.model_dump())
    session.add(contact)
    await session.commit()
    logger.info(
        "customer_contact_created id=%s customer=%s by=%s",
        contact.id,
        customer_id,
        user.id,
    )
    return _out(contact)


@router.put("/{contact_id}")
async def update_contact(
    customer_id: int,
    contact_id: int,
    body: ContactPatch,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    contact = await _contact(session, customer_id, contact_id)
    changed = sorted(body.model_fields_set)
    for name in changed:
        value = getattr(body, name)
        if value is None and name != "phone":
            raise HTTPException(status_code=422, detail=f"{name} não pode ser nulo")
        setattr(contact, name, value)
    await session.commit()
    logger.info(
        "customer_contact_updated id=%s customer=%s by=%s fields=%s",
        contact.id,
        customer_id,
        user.id,
        changed,
    )
    return _out(contact)


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(
    customer_id: int,
    contact_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    contact = await _contact(session, customer_id, contact_id)
    await session.delete(contact)
    await session.commit()
    logger.info(
        "customer_contact_deleted id=%s customer=%s by=%s",
        contact_id,
        customer_id,
        user.id,
    )
