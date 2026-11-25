-- Login do GLPI = parte local do e-mail; único de forma atômica. Só no bootstrap de banco vazio:
-- em banco existente a migração (app/migrate.py) cria o índice depois de checar colisões.
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_glpi_login ON n_infraops_users ((lower(split_part(email, '@', 1))));
