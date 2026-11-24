-- Cadastro único de pessoas e equipes (spec 2026-11-24): o Hub é a fonte, o GLPI é reconciliado.
ALTER TABLE n_infraops_users ADD COLUMN IF NOT EXISTS is_oncall BOOLEAN NOT NULL DEFAULT FALSE;
CREATE TABLE IF NOT EXISTS n_infraops_team_members (
    customer_id BIGINT NOT NULL REFERENCES n_infraops_customers(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES n_infraops_users(id) ON DELETE CASCADE,
    PRIMARY KEY (customer_id, user_id)
);
-- O login do GLPI é a parte local do e-mail: precisa ser único de forma atômica.
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_glpi_login ON n_infraops_users ((lower(split_part(email, '@', 1))));
