# Bootstrap local do banco do Hub — 2026-09-28

**Escopo:** teste descartável em Docker Desktop local. Nenhum banco ou serviço de produção foi alterado. Este resultado não aprova o gate da Fase 0.

## Ambiente e procedimento

- Imagem: `timescale/timescaledb:latest-pg16@sha256:ba149561ad4ddff5940d6eb0a0df60aefd1355cee1a450928f271267038fc888`, a mesma fixada em `app/docker-compose.yml`.
- Um container PostgreSQL 16 novo, sem volume persistente, recebeu os três arquivos de `app/backend/sql` como volume somente leitura em `/docker-entrypoint-initdb.d`, reproduzindo o mount do Compose. Os serviços existentes do Docker não foram tocados.
- O entrypoint executou `000_init.sql`, `001_schema.sql` e `002_push_subscriptions.sql` sem erro. Foram confirmadas as extensões `timescaledb` e `vector` e as tabelas `n_infraops_users`, `n_infraops_incident_actions` e `n_infraops_push_subscriptions`.
- `NINF_DATABASE_URL=... python3 -m app.migrate` concluiu sobre esse banco inicializado.
- Um segundo ensaio local na mesma imagem, com os mesmos scripts executados via `psql`, aplicou `app.migrate` duas vezes e persistiu via ORM um usuário, um incidente e uma ação; o detalhe consultou o histórico atribuído.
- Ambos os containers foram interrompidos e removidos. As cópias temporárias dos três scripts SQL foram apagadas.

## Limites

O ensaio não executou o Compose completo, nem fluxo Zabbix → GLPI, backup/restore, canário ou rollback. O gate de release continua pendente.
