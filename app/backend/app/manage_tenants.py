# -------------------------------------------------------
# n.infraops — CLI para gerenciamento de Tenants (RMM)
# -------------------------------------------------------
"""
CLI para cadastrar, listar, atualizar e remover credenciais de RMM
dos clientes (multi-tenant) na tabela n_infraops_customer_credentials.

Uso:
  python -m app.manage_tenants list
  python -m app.manage_tenants add --customer-id cliente_a --provider datto --api-key xxx --api-secret yyy --api-url zzz
  python -m app.manage_tenants delete --customer-id cliente_a --provider datto
"""

import argparse
import asyncio
import sys

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import CustomerCredentials


async def add_tenant(
    customer_id: str,
    provider: str,
    api_key: str,
    api_secret: str | None,
    api_url: str | None,
) -> None:
    """Adiciona ou atualiza as credenciais de um cliente."""
    async with SessionLocal() as session:
        async with session.begin():
            stmt = select(CustomerCredentials).where(
                CustomerCredentials.customer_id == customer_id,
                CustomerCredentials.provider == provider,
            )
            result = await session.execute(stmt)
            creds = result.scalar_one_or_none()

            if creds:
                creds.api_key = api_key
                creds.api_secret = api_secret
                creds.api_url = api_url
                print(
                    f"✅ Credenciais atualizadas para o tenant '{customer_id}' (provedor: {provider})"
                )
            else:
                creds = CustomerCredentials(
                    customer_id=customer_id,
                    provider=provider,
                    api_key=api_key,
                    api_secret=api_secret,
                    api_url=api_url,
                )
                session.add(creds)
                print(
                    f"✅ Novo tenant cadastrado: '{customer_id}' (provedor: {provider})"
                )


async def delete_tenant(customer_id: str, provider: str) -> None:
    """Deleta credenciais de um cliente."""
    async with SessionLocal() as session:
        async with session.begin():
            stmt = delete(CustomerCredentials).where(
                CustomerCredentials.customer_id == customer_id,
                CustomerCredentials.provider == provider,
            )
            result = await session.execute(stmt)
            if getattr(result, "rowcount", 0) > 0:
                print(
                    f"✅ Credenciais removidas para o tenant '{customer_id}' (provedor: {provider})"
                )
            else:
                print(
                    f"❌ Nenhuma credencial encontrada para o tenant '{customer_id}' (provedor: {provider})"
                )


async def list_tenants() -> None:
    """Lista todos os tenants cadastrados."""
    async with SessionLocal() as session:
        stmt = select(CustomerCredentials).order_by(CustomerCredentials.customer_id)
        result = await session.execute(stmt)
        creds_list = result.scalars().all()

        if not creds_list:
            print("ℹ️ Nenhum tenant cadastrado no banco de dados.")
            return

        print("\n=== Tenants cadastrados no n.infraops ===")
        print(
            f"{'Customer ID':<20} | {'Provider':<10} | {'API Key (Mascarada)':<30} | {'API URL':<40}"
        )
        print("-" * 110)
        for creds in creds_list:
            masked_key = (
                creds.api_key[:4] + "*" * (len(creds.api_key) - 8) + creds.api_key[-4:]
                if len(creds.api_key) > 8
                else "****"
            )
            print(
                f"{creds.customer_id:<20} | {creds.provider:<10} | {masked_key:<30} | {creds.api_url or '':<40}"
            )
        print("-" * 110)
        print(f"Total: {len(creds_list)} registro(s).\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="n.infraops — Gerenciador de Credenciais Multi-Tenant (RMM)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcomando Add
    parser_add = subparsers.add_parser(
        "add", help="Cadastra ou atualiza credenciais de um tenant."
    )
    parser_add.add_argument(
        "--customer-id", required=True, help="ID único do cliente (ex: cliente_corp_a)"
    )
    parser_add.add_argument(
        "--provider",
        required=True,
        choices=["datto", "atera"],
        help="Provedor RMM ('datto' ou 'atera')",
    )
    parser_add.add_argument("--api-key", required=True, help="API Key do RMM")
    parser_add.add_argument(
        "--api-secret", help="API Secret (Obrigatório para Datto RMM)"
    )
    parser_add.add_argument(
        "--api-url", help="API URL (Opcional, possui fallback nativo)"
    )

    # Subcomando Delete
    parser_delete = subparsers.add_parser(
        "delete", help="Deleta credenciais de um tenant."
    )
    parser_delete.add_argument(
        "--customer-id", required=True, help="ID único do cliente"
    )
    parser_delete.add_argument(
        "--provider", required=True, choices=["datto", "atera"], help="Provedor RMM"
    )

    # Subcomando List
    subparsers.add_parser("list", help="Lista todos os tenants cadastrados.")

    args = parser.parse_args()

    # Validação condicional para Datto
    if args.command == "add" and args.provider == "datto" and not args.api_secret:
        print(
            "❌ Erro: O provedor 'datto' exige o parâmetro --api-secret",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.command == "add":
        asyncio.run(
            add_tenant(
                args.customer_id,
                args.provider,
                args.api_key,
                args.api_secret,
                args.api_url,
            )
        )
    elif args.command == "delete":
        asyncio.run(delete_tenant(args.customer_id, args.provider))
    elif args.command == "list":
        asyncio.run(list_tenants())


if __name__ == "__main__":
    main()
