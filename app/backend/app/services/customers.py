"""Cadastro de clientes: resolve nome/apelido -> cliente e entidade GLPI."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Customer, CustomerAlias


def norm_alias(name: str) -> str:
    return name.lower().strip()


async def resolve_customer(session: AsyncSession, name: str) -> Customer | None:
    return (
        await session.execute(
            select(Customer)
            .join(CustomerAlias, CustomerAlias.customer_id == Customer.id)
            .where(CustomerAlias.alias_norm == norm_alias(name))
        )
    ).scalar_one_or_none()


async def resolve_glpi_entity_id(session: AsyncSession, customer_name: str) -> int:
    """Entidade GLPI do cliente; desconhecido ou inativo nunca cai na entidade 0."""
    customer = await resolve_customer(session, customer_name)
    if customer is None or not customer.active or customer.glpi_entity_id is None:
        raise ValueError("Cliente sem entidade GLPI mapeada; ticket recusado")
    return customer.glpi_entity_id
