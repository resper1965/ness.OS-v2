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

# Idêntico ao bloco `sla:begin/end` de sql/001_schema.sql (paridade testada).
# Sem `;` dentro de instrução: a divisão abaixo é por `;`.
SLA_SQL = """
CREATE TABLE IF NOT EXISTS n_infraops_sla_calendars (
    id        BIGSERIAL PRIMARY KEY,
    name      VARCHAR(64) NOT NULL UNIQUE,
    timezone  VARCHAR(64) NOT NULL DEFAULT 'America/Sao_Paulo',
    is_24x7   BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS n_infraops_sla_calendar_hours (
    id          BIGSERIAL PRIMARY KEY,
    calendar_id BIGINT NOT NULL REFERENCES n_infraops_sla_calendars(id) ON DELETE CASCADE,
    weekday     SMALLINT NOT NULL,
    start_time  TIME NOT NULL,
    end_time    TIME NOT NULL,
    CONSTRAINT ck_sla_hours_weekday CHECK (weekday BETWEEN 0 AND 6),
    CONSTRAINT ck_sla_hours_range CHECK (start_time < end_time)
);
CREATE TABLE IF NOT EXISTS n_infraops_sla_holidays (
    id           BIGSERIAL PRIMARY KEY,
    calendar_id  BIGINT NOT NULL REFERENCES n_infraops_sla_calendars(id) ON DELETE CASCADE,
    holiday_date DATE NOT NULL,
    name         VARCHAR(128) NOT NULL,
    CONSTRAINT uq_sla_holidays_calendar_date UNIQUE (calendar_id, holiday_date)
);
CREATE TABLE IF NOT EXISTS n_infraops_contracts (
    id                 BIGSERIAL PRIMARY KEY,
    tenant_id          VARCHAR(128),
    is_default         BOOLEAN NOT NULL DEFAULT FALSE,
    contractual        BOOLEAN NOT NULL DEFAULT TRUE,
    name               VARCHAR(255) NOT NULL,
    modality           VARCHAR(32),
    status             VARCHAR(16) NOT NULL DEFAULT 'draft',
    starts_on          DATE,
    ends_on            DATE,
    calendar_id        BIGINT REFERENCES n_infraops_sla_calendars(id),
    notes              TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by_user_id BIGINT,
    CONSTRAINT ck_contracts_modality CHECK (modality IS NULL OR modality IN ('managed', 'onsite', 'shared')),
    CONSTRAINT ck_contracts_status CHECK (status IN ('draft', 'active', 'suspended', 'ended')),
    CONSTRAINT ck_contracts_dates CHECK (starts_on IS NULL OR ends_on IS NULL OR starts_on <= ends_on),
    CONSTRAINT ck_contracts_default CHECK (
        (is_default AND tenant_id IS NULL AND NOT contractual AND status = 'active')
        OR (NOT is_default AND tenant_id IS NOT NULL AND contractual)
    )
);
DROP INDEX IF EXISTS uq_contracts_tenant_active;
CREATE UNIQUE INDEX IF NOT EXISTS uq_contracts_tenant_active_ci ON n_infraops_contracts (lower(tenant_id)) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS uq_contracts_default ON n_infraops_contracts (is_default) WHERE is_default;
CREATE TABLE IF NOT EXISTS n_infraops_sla_policies (
    id                 BIGSERIAL PRIMARY KEY,
    contract_id        BIGINT NOT NULL REFERENCES n_infraops_contracts(id) ON DELETE CASCADE,
    key                VARCHAR(32) NOT NULL,
    name               VARCHAR(128) NOT NULL,
    min_severity       SMALLINT,
    severity           SMALLINT,
    has_tenant         BOOLEAN,
    ack_minutes        INTEGER NOT NULL,
    tto_minutes        INTEGER,
    ttr_minutes        INTEGER,
    calendar_id        BIGINT REFERENCES n_infraops_sla_calendars(id),
    enabled            BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by_user_id BIGINT,
    CONSTRAINT uq_sla_policies_contract_key UNIQUE (contract_id, key),
    CONSTRAINT ck_sla_policies_ack CHECK (ack_minutes BETWEEN 1 AND 43200),
    CONSTRAINT ck_sla_policies_tto CHECK (tto_minutes IS NULL OR tto_minutes BETWEEN 1 AND 43200),
    CONSTRAINT ck_sla_policies_ttr CHECK (ttr_minutes IS NULL OR ttr_minutes BETWEEN 1 AND 43200)
);
CREATE TABLE IF NOT EXISTS n_infraops_escalation_steps (
    id                 BIGSERIAL PRIMARY KEY,
    contract_id        BIGINT NOT NULL REFERENCES n_infraops_contracts(id) ON DELETE CASCADE,
    position           SMALLINT NOT NULL,
    role               VARCHAR(32) NOT NULL,
    enabled            BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by_user_id BIGINT,
    CONSTRAINT uq_escalation_steps_contract_position UNIQUE (contract_id, position)
);
CREATE TABLE IF NOT EXISTS n_infraops_contract_changes (
    id                 BIGSERIAL PRIMARY KEY,
    contract_id        BIGINT NOT NULL REFERENCES n_infraops_contracts(id),
    changed_by_user_id BIGINT,
    changed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    entity             VARCHAR(32) NOT NULL,
    before             JSONB,
    after              JSONB
);
CREATE INDEX IF NOT EXISTS ix_contract_changes_contract ON n_infraops_contract_changes (contract_id, changed_at DESC);
WITH c AS (
    INSERT INTO n_infraops_sla_calendars (name, is_24x7)
    VALUES ('24x7', TRUE), ('comercial', FALSE)
    ON CONFLICT (name) DO NOTHING
    RETURNING id, name
)
INSERT INTO n_infraops_sla_calendar_hours (calendar_id, weekday, start_time, end_time)
SELECT c.id, d, '08:00', '20:00' FROM c, generate_series(0, 4) AS d WHERE c.name = 'comercial';
WITH cal AS (
    SELECT (SELECT id FROM n_infraops_sla_calendars WHERE name = '24x7') AS h24,
           (SELECT id FROM n_infraops_sla_calendars WHERE name = 'comercial') AS biz
), c AS (
    INSERT INTO n_infraops_contracts (is_default, contractual, name, status, calendar_id)
    SELECT TRUE, FALSE, 'Padrão interno ness. (NÃO contratual)', 'active', biz FROM cal
    ON CONFLICT DO NOTHING
    RETURNING id
), p AS (
    INSERT INTO n_infraops_sla_policies
        (contract_id, key, name, min_severity, severity, has_tenant, ack_minutes, tto_minutes, ttr_minutes, calendar_id)
    SELECT c.id, v.key, v.name, v.min_sev, v.sev, v.has_tenant, v.ack, v.tto, v.ttr,
           CASE v.calk WHEN 'h24' THEN cal.h24 ELSE cal.biz END
    FROM c, cal, (VALUES
        ('critical', 'Crítica', NULL::int, 5, TRUE, 15, 15, 240, 'h24'),
        ('elevated', 'Alta', NULL, 4, TRUE, 60, 30, 480, 'h24'),
        ('no_client', 'Sem cliente', 4, NULL, FALSE, 720, NULL, NULL, 'biz')
    ) AS v(key, name, min_sev, sev, has_tenant, ack, tto, ttr, calk)
    RETURNING 1
)
INSERT INTO n_infraops_escalation_steps (contract_id, position, role)
SELECT c.id, v.position, v.role FROM c, (VALUES (1, 'soc'), (2, 'noc'), (3, 'operator'), (4, 'admin')) AS v(position, role);
"""


# Parâmetros da política de atendimento (padrão = linhas do contrato padrão, NÃO contratual)
# e parâmetros globais da plataforma. Idêntico ao bloco `params:begin/end` de 001_schema.sql.
PARAMS_SQL = """
CREATE TABLE IF NOT EXISTS n_infraops_contract_policy_params (
    contract_id        BIGINT NOT NULL REFERENCES n_infraops_contracts(id) ON DELETE CASCADE,
    key                VARCHAR(48) NOT NULL,
    value_int          INTEGER NOT NULL,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by_user_id BIGINT,
    PRIMARY KEY (contract_id, key),
    CONSTRAINT ck_policy_params_value CHECK (value_int > 0),
    CONSTRAINT ck_policy_params_ceiling CHECK (
        (key <> 'soc_attend_min_level' OR value_int <= 12)
        AND (key <> 'soc_archive_score_floor' OR value_int <= 75)
        AND (key <> 'ot_retrospective_hours' OR value_int <= 24)
        AND (key <> 'weekly_sample_pct' OR value_int BETWEEN 10 AND 100)
        AND (key <> 'weekly_sample_per_client' OR value_int >= 20)
    )
);
CREATE TABLE IF NOT EXISTS n_infraops_platform_params (
    key                VARCHAR(48) PRIMARY KEY,
    value_int          INTEGER NOT NULL,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by_user_id BIGINT,
    CONSTRAINT ck_platform_params_value CHECK (value_int > 0),
    CONSTRAINT ck_platform_params_probe CHECK (key <> 'probe_timeout_seconds' OR value_int <= 22)
);
INSERT INTO n_infraops_contract_policy_params (contract_id, key, value_int)
SELECT c.id, v.key, v.value_int
FROM n_infraops_contracts c, (VALUES
    ('soc_attend_min_level', 12),
    ('soc_archive_score_floor', 75),
    ('ot_retrospective_hours', 24),
    ('weekly_sample_per_client', 20),
    ('weekly_sample_pct', 10),
    ('weekly_sample_threshold', 200)
) AS v(key, value_int)
WHERE c.is_default
ON CONFLICT (contract_id, key) DO NOTHING;
INSERT INTO n_infraops_platform_params (key, value_int)
VALUES
    ('source_max_age_seconds', 900),
    ('queue_max_age_seconds', 300),
    ('worker_failure_window_seconds', 900),
    ('probe_timeout_seconds', 20)
ON CONFLICT (key) DO NOTHING;
"""


async def apply_sla_sql(conn):
    for stmt in SLA_SQL.split(";"):
        if stmt.strip():
            await conn.execute(text(stmt))


async def apply_params_sql(conn):
    for stmt in PARAMS_SQL.split(";"):
        if stmt.strip():
            await conn.execute(text(stmt))


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

        # Cadastro de clientes e apelidos; seed só para cliente novo (edição não é desfeita).
        for ddl in (
            """CREATE TABLE IF NOT EXISTS n_infraops_customers (
    id                 BIGSERIAL PRIMARY KEY,
    key                VARCHAR(64) NOT NULL UNIQUE,
    display_name       VARCHAR(255) NOT NULL,
    glpi_entity_id     INTEGER,
    active             BOOLEAN NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by_user_id BIGINT
)""",
            """CREATE TABLE IF NOT EXISTS n_infraops_customer_aliases (
    alias_norm  TEXT PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES n_infraops_customers(id) ON DELETE CASCADE
)""",
            """CREATE INDEX IF NOT EXISTS ix_n_infraops_customer_aliases_customer_id ON n_infraops_customer_aliases (customer_id)""",
            """CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_active_entity ON n_infraops_customers (glpi_entity_id) WHERE active""",
            """WITH seeded AS (
    INSERT INTO n_infraops_customers (key, display_name, glpi_entity_id)
    VALUES
        ('alupar', 'Alupar', 1),
        ('tbe', 'TBE', 2),
        ('target', 'Target', 3),
        ('ltb', 'LTB', 4),
        ('alupar-pe', 'Alupar PE', 5),
        ('alupar-co', 'Alupar CO', 6),
        ('bichara', 'Bichara', 7),
        ('cavan', 'Cavan', 8),
        ('nova-energia', 'Nova Energia', 9),
        ('numen', 'Numen IT', 10),
        ('tne', 'TNE', 11),
        ('unimed', 'Unimed', 12),
        ('ness', 'Ness', 0)
    ON CONFLICT (key) DO NOTHING
    RETURNING id, key
)
INSERT INTO n_infraops_customer_aliases (alias_norm, customer_id)
SELECT v.alias_norm, seeded.id
FROM (VALUES
    ('alupar', 'alupar'),
    ('alupar investimento s.a.', 'alupar'),
    ('tbe', 'tbe'),
    ('target', 'target'),
    ('target trading', 'target'),
    ('ltb', 'ltb'),
    ('leite tosto', 'ltb'),
    ('leite tosto e barros adv ass', 'ltb'),
    ('alupar pe', 'alupar-pe'),
    ('alupar-pe', 'alupar-pe'),
    ('alupar co', 'alupar-co'),
    ('alupar-co', 'alupar-co'),
    ('bichara', 'bichara'),
    ('cavan', 'cavan'),
    ('nova energia', 'nova-energia'),
    ('novaenergia', 'nova-energia'),
    ('numen', 'numen'),
    ('numen it', 'numen'),
    ('tne', 'tne'),
    ('unimed', 'unimed'),
    ('ness', 'ness'),
    ('ness processos e tecnologia ltda.', 'ness')
) AS v(alias_norm, key)
JOIN seeded ON seeded.key = v.key
ON CONFLICT DO NOTHING""",
            """CREATE TABLE IF NOT EXISTS n_infraops_hostgroup_rules (
    id                           BIGSERIAL PRIMARY KEY,
    pattern                      TEXT,
    customer_id                  BIGINT NOT NULL REFERENCES n_infraops_customers(id) ON DELETE CASCADE,
    ignore_when_with_customer_id BIGINT REFERENCES n_infraops_customers(id) ON DELETE CASCADE,
    priority                     INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT ck_hostgroup_rule_kind CHECK (pattern IS NOT NULL OR ignore_when_with_customer_id IS NOT NULL),
    CONSTRAINT ck_hostgroup_rule_pattern CHECK (pattern IS NULL OR btrim(pattern) <> ''),
    CONSTRAINT ck_hostgroup_rule_self CHECK (ignore_when_with_customer_id IS DISTINCT FROM customer_id)
)""",
            """DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_hostgroup_rule_pattern') THEN
        ALTER TABLE n_infraops_hostgroup_rules ADD CONSTRAINT ck_hostgroup_rule_pattern CHECK (pattern IS NULL OR btrim(pattern) <> '');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_hostgroup_rule_self') THEN
        ALTER TABLE n_infraops_hostgroup_rules ADD CONSTRAINT ck_hostgroup_rule_self CHECK (ignore_when_with_customer_id IS DISTINCT FROM customer_id);
    END IF;
END $$""",
            """CREATE UNIQUE INDEX IF NOT EXISTS uq_hostgroup_rules ON n_infraops_hostgroup_rules (COALESCE(pattern, ''), customer_id, COALESCE(ignore_when_with_customer_id, 0))""",
            """INSERT INTO n_infraops_hostgroup_rules (pattern, customer_id, ignore_when_with_customer_id, priority)
SELECT v.pattern, c.id, w.id, v.priority
FROM (VALUES
    ('Zabbix servers', 'ness', NULL, 0),
    ('UAT sintético', 'ness', NULL, 0),
    (NULL, 'alupar', 'alupar-pe', 10),
    (NULL, 'alupar', 'alupar-co', 10)
) AS v(pattern, ckey, wkey, priority)
JOIN n_infraops_customers c ON c.key = v.ckey
LEFT JOIN n_infraops_customers w ON w.key = v.wkey
WHERE NOT EXISTS (SELECT 1 FROM n_infraops_hostgroup_rules)
ON CONFLICT DO NOTHING""",
            """CREATE TABLE IF NOT EXISTS n_infraops_customer_contacts (
    id                  BIGSERIAL PRIMARY KEY,
    customer_id         BIGINT NOT NULL REFERENCES n_infraops_customers(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    email               VARCHAR(320) NOT NULL,
    phone               VARCHAR(64),
    role                VARCHAR(64) NOT NULL,
    notify_severity_min INTEGER NOT NULL,
    active              BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT ck_customer_contacts_severity CHECK (notify_severity_min BETWEEN 1 AND 5)
)""",
            """CREATE INDEX IF NOT EXISTS ix_n_infraops_customer_contacts_customer_id ON n_infraops_customer_contacts (customer_id)""",
            # Problemas ativos do Zabbix -> incidente/cliente/chamado (tela Monitoramento).
            """CREATE INDEX IF NOT EXISTS ix_incidents_zabbix_event ON n_infraops_incidents ((tags->>'ninf_zabbix_event_id'))""",
        ):
            await conn.execute(text(ddl))
        await apply_sla_sql(conn)
        await apply_params_sql(conn)

    logger.info("Migração de banco de dados concluída com sucesso.")


if __name__ == "__main__":
    asyncio.run(run_migrations())
