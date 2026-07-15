-- =========================================================
-- n.infraops — DDL: Tabela de Subscrições do Web Push (PWA)
-- E atualizações de tabelas existentes (Fase 4.1)
-- =========================================================

-- 1. Garantir que a coluna tenant_id existe na tabela de usuários
ALTER TABLE n_infraops_users ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(128);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON n_infraops_users (tenant_id);

-- 2. Criar a tabela de subscrições para notificações push
CREATE TABLE IF NOT EXISTS n_infraops_push_subscriptions (
    id              BIGSERIAL       PRIMARY KEY,
    tenant_id       VARCHAR(128)    NOT NULL,
    user_id         BIGINT          REFERENCES n_infraops_users(id) ON DELETE CASCADE,
    endpoint        TEXT            NOT NULL UNIQUE,
    auth_key        VARCHAR(255)    NOT NULL,
    p256dh_key      VARCHAR(255)    NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Índices para otimização de consultas por tenant
CREATE INDEX IF NOT EXISTS idx_push_subs_tenant ON n_infraops_push_subscriptions (tenant_id);
