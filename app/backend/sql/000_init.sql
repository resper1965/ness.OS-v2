-- -------------------------------------------------------
-- NessOps — PostgreSQL: Configuração de acesso Docker
-- Executado pelo entrypoint ao criar o banco pela 1ª vez
-- -------------------------------------------------------

-- Permitir conexões TCP da rede Docker (172.16.0.0/12 cobre 172.x.x.x)
-- Nota: pg_hba.conf no volume pode ser editado manualmente se necessário
-- Este script é apenas documentação — o pg_hba.conf é configurado via volume

-- Garantir que a extensão TimescaleDB está ativada
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS vector;
