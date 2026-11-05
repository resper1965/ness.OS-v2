# -------------------------------------------------------
# n.infraops — Script de Migração do Banco de Dados
# -------------------------------------------------------
from __future__ import annotations

# Imports da aplicação ocorrem após o bootstrap de `sys.path` deste script.
# ruff: noqa: E402
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nessops.migration")


async def run_migrations():
    logger.info("Iniciando migração de banco de dados no Postgres...")

    async with engine.begin() as conn:
        # 1. Garantir o papel global aprovado antes de sincronizar usuários OIDC.
        logger.info("Verificando role platform_admin...")
        await conn.execute(
            text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'platform_admin';")
        )
        await conn.execute(
            text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'operator';")
        )
        await conn.execute(
            text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'viewer';")
        )

        # 2. Adicionar tenant_id em n_infraops_users se não existir
        logger.info("Verificando coluna tenant_id na tabela n_infraops_users...")
        try:
            await conn.execute(
                text(
                    "ALTER TABLE n_infraops_users ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(128);"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_users_tenant ON n_infraops_users (tenant_id);"
                )
            )
            logger.info("Coluna e índice tenant_id verificados/criados com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao verificar/criar coluna tenant_id: {e}")
            raise

        await conn.execute(
            text(
                "ALTER TABLE n_infraops_users "
                "ADD COLUMN IF NOT EXISTS session_epoch BIGINT NOT NULL DEFAULT 0;"
            )
        )

        await conn.execute(
            text(
                "ALTER TABLE n_infraops_incidents "
                "ADD COLUMN IF NOT EXISTS assigned_user_id BIGINT;"
            )
        )
        # Cliente pendente de revisão grava customer_id nulo; dedup_key torna o replay idempotente.
        for ddl in (
            "ALTER TABLE n_secops_soc_decisions ALTER COLUMN customer_id DROP NOT NULL;",
            "ALTER TABLE n_secops_soc_decisions ADD COLUMN IF NOT EXISTS dedup_key VARCHAR(64);",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_soc_decisions_dedup "
            "ON n_secops_soc_decisions (dedup_key) WHERE dedup_key IS NOT NULL;",
            "ALTER TABLE n_secops_soc_decisions ADD COLUMN IF NOT EXISTS freq_key VARCHAR(64);",
            "CREATE INDEX IF NOT EXISTS ix_soc_decisions_freq "
            "ON n_secops_soc_decisions (freq_key, created_at);",
            "ALTER TABLE n_secops_soc_decisions ADD COLUMN IF NOT EXISTS incident_id BIGINT;",
            "CREATE INDEX IF NOT EXISTS ix_soc_decisions_incident "
            "ON n_secops_soc_decisions (incident_id) WHERE incident_id IS NOT NULL;",
            "CREATE INDEX IF NOT EXISTS ix_soc_decisions_action_created "
            "ON n_secops_soc_decisions (action_taken, created_at);",
            "CREATE INDEX IF NOT EXISTS ix_soc_decisions_created "
            "ON n_secops_soc_decisions (created_at DESC);",
        ):
            await conn.execute(text(ddl))
        # Modalidade por cliente x origem; nula = pendente_de_modalidade (sem backfill).
        for ddl in (
            "ALTER TABLE n_infraops_tenant_mappings "
            "ADD COLUMN IF NOT EXISTS modality VARCHAR(32);",
            "ALTER TABLE n_infraops_tenant_mappings "
            "ADD COLUMN IF NOT EXISTS operator VARCHAR(128);",
            "ALTER TABLE n_infraops_tenant_mappings "
            "DROP CONSTRAINT IF EXISTS ck_tenant_mappings_modality;",
            "UPDATE n_infraops_tenant_mappings SET modality = CASE modality "
            "WHEN 'central_ness' THEN 'managed' "
            "WHEN 'sonda_no_cliente' THEN 'onsite' "
            "WHEN 'cliente_gerenciado' THEN 'shared' END "
            "WHERE modality IN ('central_ness', 'sonda_no_cliente', 'cliente_gerenciado');",
            """
            ALTER TABLE n_infraops_tenant_mappings
            ADD CONSTRAINT ck_tenant_mappings_modality CHECK (
                modality IS NULL OR modality IN ('managed', 'onsite', 'shared')
            );
            """,
        ):
            await conn.execute(text(ddl))
        actions_ddl = """
                CREATE TABLE IF NOT EXISTS n_infraops_incident_actions (
                    id BIGSERIAL PRIMARY KEY,
                    incident_id BIGINT NOT NULL REFERENCES n_infraops_incidents(id),
                    actor_user_id BIGINT,
                    actor_source VARCHAR(32) NOT NULL,
                    action VARCHAR(32) NOT NULL,
                    previous_status VARCHAR(32),
                    new_status VARCHAR(32),
                    previous_assignee_id BIGINT,
                    new_assignee_id BIGINT,
                    note TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
        await conn.execute(text(actions_ddl))
        reservation_ddl = (
            backend_root / "sql" / "003_glpi_ticket_post_reservations.sql"
        ).read_text(encoding="utf-8")
        await conn.execute(text(reservation_ddl))
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_incident_actions_incident_created "
                "ON n_infraops_incident_actions (incident_id, created_at DESC);"
            )
        )

        # 3. Criar tabela n_infraops_push_subscriptions se não existir
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
            logger.info(
                "Tabela e índice n_infraops_push_subscriptions verificados/criados com sucesso."
            )
        except Exception as e:
            logger.error(
                f"Erro ao verificar/criar tabela n_infraops_push_subscriptions: {e}"
            )
            raise

        notifications_ddl = """
            CREATE TABLE IF NOT EXISTS n_infraops_notifications (
                id                      BIGSERIAL PRIMARY KEY,
                incident_id             BIGINT NOT NULL REFERENCES n_infraops_incidents(id),
                user_id                 BIGINT NOT NULL REFERENCES n_infraops_users(id),
                channel                 VARCHAR(16) NOT NULL,
                step                    SMALLINT NOT NULL,
                created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                claimed_at              TIMESTAMPTZ,
                attempts                SMALLINT NOT NULL DEFAULT 0,
                sent_at                 TIMESTAMPTZ,
                provider_result         TEXT,
                acknowledged_at         TIMESTAMPTZ,
                ack_type                VARCHAR(16),
                acknowledged_by_user_id BIGINT,
                resolved_at             TIMESTAMPTZ,
                CONSTRAINT uq_notifications_slot UNIQUE (incident_id, user_id, channel, step),
                CONSTRAINT ck_notifications_channel CHECK (channel IN ('email', 'push'))
            );
            """
        await conn.execute(text(notifications_ddl))

        # ADR 0015: vínculo (issuer, subject) -> usuário local.
        for ddl in (
            """CREATE TABLE IF NOT EXISTS n_infraops_identities (
    id                 BIGSERIAL PRIMARY KEY,
    issuer             VARCHAR(512) NOT NULL,
    subject            VARCHAR(255) NOT NULL,
    user_id            BIGINT NOT NULL REFERENCES n_infraops_users(id),
    created_by_user_id BIGINT REFERENCES n_infraops_users(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_identities_iss_sub UNIQUE (issuer, subject)
)""",
            """CREATE INDEX IF NOT EXISTS ix_n_infraops_identities_user_id ON n_infraops_identities (user_id);""",
        ):
            await conn.execute(text(ddl))

    logger.info("Migração de banco de dados concluída com sucesso.")


if __name__ == "__main__":
    asyncio.run(run_migrations())
