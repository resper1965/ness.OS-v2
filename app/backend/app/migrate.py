# -------------------------------------------------------
# n.infraops — Script de Migração do Banco de Dados
# -------------------------------------------------------
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Ajustar sys.path para permitir imports de app (grandparent de migrate.py)
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from sqlalchemy import text
from app.database import engine
# Importar os modelos para registro no Base
from app.models.users import User
from app.models.push import PushSubscription

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nessops.migration")


async def run_migrations():
    logger.info("Iniciando migração de banco de dados no Postgres...")
    
    async with engine.begin() as conn:
        # 1. Adicionar tenant_id em n_infraops_users se não existir
        logger.info("Verificando coluna tenant_id na tabela n_infraops_users...")
        try:
            await conn.execute(
                text("ALTER TABLE n_infraops_users ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(128);")
            )
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_users_tenant ON n_infraops_users (tenant_id);")
            )
            logger.info("Coluna e índice tenant_id verificados/criados com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao verificar/criar coluna tenant_id: {e}")
            raise

        # 2. Criar tabela n_infraops_push_subscriptions se não existir
        logger.info("Verificando tabela n_infraops_push_subscriptions...")
        try:
            ddl = """
            CREATE TABLE IF NOT EXISTS n_infraops_push_subscriptions (
                id              BIGSERIAL       PRIMARY KEY,
                tenant_id       VARCHAR(128)    NOT NULL,
                user_id         BIGINT          REFERENCES n_infraops_users(id) ON DELETE CASCADE,
                endpoint        TEXT            NOT NULL UNIQUE,
                auth_key        VARCHAR(255)    NOT NULL,
                p256dh_key      VARCHAR(255)    NOT NULL,
                created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
            );
            """
            await conn.execute(text(ddl))
            
            idx_ddl = "CREATE INDEX IF NOT EXISTS idx_push_subs_tenant ON n_infraops_push_subscriptions (tenant_id);"
            await conn.execute(text(idx_ddl))
            logger.info("Tabela e índice n_infraops_push_subscriptions verificados/criados com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao verificar/criar tabela n_infraops_push_subscriptions: {e}")
            raise
            
    logger.info("Migração de banco de dados concluída com sucesso.")


if __name__ == "__main__":
    asyncio.run(run_migrations())
