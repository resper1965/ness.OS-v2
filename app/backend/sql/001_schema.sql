-- =========================================================
-- n.infraops — DDL: Tabela de Ativos (Multi-RMM Híbrido)
-- PostgreSQL 16 + TimescaleDB + pgvector
-- =========================================================

-- ENUMs para tipagem forte no banco
CREATE TYPE asset_type AS ENUM (
    'windows',
    'linux',
    'network_device'
);

CREATE TYPE rmm_provider AS ENUM (
    'datto',
    'atera',
    'none'           -- Switches, firewalls, APs — sem agente RMM
);

CREATE TYPE asset_status AS ENUM (
    'active',
    'maintenance',
    'decommissioned'
);


-- ---------------------------------------------------------
-- Tabela principal de ativos
-- Cada ativo mapeia:
--   1. Identidade no Zabbix (host_id)
--   2. Identidade no RMM (rmm_device_id) — pode ser null
--   3. Estratégia de execução de playbooks (via rmm_provider)
-- ---------------------------------------------------------
CREATE TABLE n_infraops_assets (
    id              BIGSERIAL       PRIMARY KEY,

    -- Identidade Zabbix (source of truth)
    zabbix_host_id  VARCHAR(64)     NOT NULL UNIQUE,
    hostname        VARCHAR(255)    NOT NULL,
    ip_address      INET,
    fqdn            VARCHAR(512),

    -- Classificação do ativo
    asset_type      asset_type      NOT NULL DEFAULT 'linux',
    status          asset_status    NOT NULL DEFAULT 'active',

    -- Multi-RMM: qual provedor gerencia este ativo?
    rmm_provider    rmm_provider    NOT NULL DEFAULT 'none',
    rmm_device_id   VARCHAR(128),       -- ID do device na API do RMM
    rmm_site_id     VARCHAR(128),       -- Site/tenant no RMM (multi-tenant)

    -- Metadados operacionais
    os_family       VARCHAR(64),        -- 'Windows Server 2022', 'Debian 12', 'Cisco IOS'
    os_version      VARCHAR(64),
    customer_id     VARCHAR(128),       -- ID do cliente/contrato (multi-tenant)
    customer_name   VARCHAR(255),
    location        VARCHAR(255),       -- Datacenter, filial, rack
    tags            JSONB           DEFAULT '{}',

    -- Credenciais de acesso para network_device (SSH)
    -- Armazenadas aqui como referência; em produção usar Vault/SOPS
    ssh_port        INTEGER         DEFAULT 22,
    ssh_username    VARCHAR(64),

    -- Controle
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_seen       TIMESTAMPTZ,        -- Último check-in do Zabbix

    -- Constraints
    CONSTRAINT chk_rmm_device_id CHECK (
        -- Se tem RMM, DEVE ter device_id
        (rmm_provider = 'none') OR (rmm_device_id IS NOT NULL)
    ),
    CONSTRAINT chk_network_ssh CHECK (
        -- Network devices devem ter username SSH
        (asset_type != 'network_device') OR (ssh_username IS NOT NULL)
    )
);

-- Índices de busca frequente
CREATE INDEX idx_assets_zabbix_host    ON n_infraops_assets (zabbix_host_id);
CREATE INDEX idx_assets_rmm_provider   ON n_infraops_assets (rmm_provider) WHERE status = 'active';
CREATE INDEX idx_assets_customer       ON n_infraops_assets (customer_id);
CREATE INDEX idx_assets_type_status    ON n_infraops_assets (asset_type, status);
CREATE INDEX idx_assets_tags           ON n_infraops_assets USING GIN (tags);

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_assets_updated_at
    BEFORE UPDATE ON n_infraops_assets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ---------------------------------------------------------
-- Tabela de incidentes (referenciada pelo boilerplate)
-- ---------------------------------------------------------
CREATE TABLE n_infraops_incidents (
    id              BIGSERIAL       PRIMARY KEY,
    fingerprint     VARCHAR(64)     NOT NULL UNIQUE,  -- SHA-256
    title           VARCHAR(512)    NOT NULL,
    severity        SMALLINT        NOT NULL DEFAULT 3,
    status          VARCHAR(32)     NOT NULL DEFAULT 'open',

    -- Referências
    host_id         VARCHAR(64)     NOT NULL,
    host_name       VARCHAR(255)    NOT NULL,
    trigger_id      VARCHAR(64)     NOT NULL,
    asset_id        BIGINT          REFERENCES n_infraops_assets(id),

    -- Contadores e timestamps
    alert_count     INTEGER         NOT NULL DEFAULT 1,
    first_seen      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_seen       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Dados sanitizados
    sanitized_description TEXT      DEFAULT '',
    tags            JSONB           DEFAULT '{}',

    -- Ticketing
    deskmanager_ticket_id VARCHAR(64),

    -- Controle
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_incidents_fingerprint ON n_infraops_incidents (fingerprint);
CREATE INDEX idx_incidents_status      ON n_infraops_incidents (status) WHERE status != 'resolved';
CREATE INDEX idx_incidents_host        ON n_infraops_incidents (host_id);
CREATE INDEX idx_incidents_last_seen   ON n_infraops_incidents (last_seen DESC);

CREATE TRIGGER trg_incidents_updated_at
    BEFORE UPDATE ON n_infraops_incidents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ---------------------------------------------------------
-- Tabela de relatórios pós-incidente (post-mortem)
-- ---------------------------------------------------------
CREATE TABLE n_infraops_incident_reports (
    id                      BIGSERIAL       PRIMARY KEY,
    incident_fingerprint    VARCHAR(64)     NOT NULL REFERENCES n_infraops_incidents(fingerprint),
    deskmanager_ticket_id   VARCHAR(64),

    -- Conteúdo gerado pelo Gemini
    markdown_report         TEXT            NOT NULL,
    summary                 TEXT            NOT NULL,
    root_cause              TEXT            NOT NULL,
    blast_radius            JSONB           DEFAULT '[]',
    corrective_actions      JSONB           DEFAULT '[]',
    timeline                JSONB           DEFAULT '[]',

    -- Embedding para busca por similaridade (pgvector)
    embedding               vector(768),    -- Gemini embedding dimension

    -- Metadados da geração
    gemini_model_used       VARCHAR(64),
    prompt_tokens           INTEGER         DEFAULT 0,
    completion_tokens       INTEGER         DEFAULT 0,

    -- Controle
    generated_at            TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reports_fingerprint ON n_infraops_incident_reports (incident_fingerprint);

-- Índice HNSW para busca de similaridade (incidentes parecidos)
CREATE INDEX idx_reports_embedding ON n_infraops_incident_reports
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- ---------------------------------------------------------
-- Tabela de execuções de playbooks (audit trail)
-- ---------------------------------------------------------
CREATE TABLE n_infraops_playbook_executions (
    id              BIGSERIAL       PRIMARY KEY,
    incident_id     BIGINT          REFERENCES n_infraops_incidents(id),
    asset_id        BIGINT          REFERENCES n_infraops_assets(id),

    -- Playbook
    playbook_name   VARCHAR(128)    NOT NULL,
    rmm_provider    rmm_provider    NOT NULL,
    execution_mode  VARCHAR(32)     NOT NULL DEFAULT 'manual',  -- 'manual', 'auto', 'dry_run'

    -- Resultado
    status          VARCHAR(32)     NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'running', 'success', 'failed', 'rolled_back'
    approved_by     VARCHAR(128),       -- Slack user ID
    approved_at     TIMESTAMPTZ,
    output          TEXT,
    error_message   TEXT,

    -- Controle
    started_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER
);

CREATE INDEX idx_executions_incident ON n_infraops_playbook_executions (incident_id);
CREATE INDEX idx_executions_asset    ON n_infraops_playbook_executions (asset_id);
CREATE INDEX idx_executions_status   ON n_infraops_playbook_executions (status) WHERE status IN ('pending', 'running');

-- ---------------------------------------------------------
-- Tabela de métricas (TimescaleDB hypertable)
-- ---------------------------------------------------------
CREATE TABLE n_infraops_metrics (
    ts              TIMESTAMPTZ     NOT NULL,
    host_id         VARCHAR(64)     NOT NULL,
    item_id         VARCHAR(64)     NOT NULL,
    item_key        VARCHAR(255)    NOT NULL,
    value           DOUBLE PRECISION NOT NULL
);

-- Converter para hypertable se TimescaleDB estiver disponível
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('n_infraops_metrics', 'ts', if_not_exists => TRUE);
    END IF;
END $$;

CREATE INDEX idx_metrics_host_key_ts ON n_infraops_metrics (host_id, item_key, ts DESC);

-- ---------------------------------------------------------
-- Tabela de credenciais de clientes (Multi-tenant)
-- ---------------------------------------------------------
CREATE TABLE n_infraops_customer_credentials (
    id              BIGSERIAL       PRIMARY KEY,
    customer_id     VARCHAR(128)    NOT NULL,
    provider        VARCHAR(64)     NOT NULL, -- 'datto', 'atera'
    api_key         VARCHAR(255)    NOT NULL,
    api_secret      VARCHAR(255),             -- Opcional (ex: Datto usa secret, Atera não)
    api_url         VARCHAR(512),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_customer_provider UNIQUE (customer_id, provider)
);

CREATE INDEX idx_credentials_customer ON n_infraops_customer_credentials (customer_id);

CREATE TRIGGER trg_credentials_updated_at
    BEFORE UPDATE ON n_infraops_customer_credentials
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
