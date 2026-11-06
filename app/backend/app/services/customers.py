"""Cadastro de clientes: resolve nome/apelido -> cliente e entidade GLPI."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Customer, CustomerAlias


class AmbiguousCustomer(ValueError):
    """O mesmo nome pertence a mais de um cliente; nunca escolhe um."""


def norm_alias(name: str) -> str:
    return name.lower().strip()


async def matching_customers(session: AsyncSession, name: str) -> list[Customer]:
    """Clientes cujo apelido, nome de exibição ou chave (normalizados) é `name`."""
    n = norm_alias(name)
    alias_ids = select(CustomerAlias.customer_id).where(CustomerAlias.alias_norm == n)
    return list(
        (
            await session.execute(
                select(Customer)
                .where(
                    or_(
                        Customer.id.in_(alias_ids),
                        func.lower(func.trim(Customer.display_name)) == n,
                        func.lower(Customer.key) == n,
                    )
                )
                .order_by(Customer.id)
            )
        ).scalars()
    )


async def resolve_customer(session: AsyncSession, name: str) -> Customer | None:
    found = await matching_customers(session, name)
    if len(found) > 1:
        raise AmbiguousCustomer("Nome associado a clientes distintos; ticket recusado")
    return found[0] if found else None


async def resolve_active_customer(session: AsyncSession, name: str) -> Customer:
    """Cliente ativo com entidade GLPI; desconhecido ou inativo nunca cai na entidade 0."""
    customer = await resolve_customer(session, name)
    if customer is None or not customer.active or customer.glpi_entity_id is None:
        raise ValueError("Cliente sem entidade GLPI mapeada; ticket recusado")
    return customer


async def resolve_glpi_entity_id(session: AsyncSession, customer_name: str) -> int:
    customer = await resolve_active_customer(session, customer_name)
    assert customer.glpi_entity_id is not None
    return customer.glpi_entity_id
