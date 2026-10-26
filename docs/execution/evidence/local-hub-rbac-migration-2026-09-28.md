# Papéis `operator` e `viewer` — migração local

**Escopo:** dois bancos PostgreSQL 16/TimescaleDB descartáveis no Docker Desktop local, usando a imagem fixada em `app/docker-compose.yml`. Nenhuma identidade ou banco de produção foi alterado.

1. Banco novo: `000_init.sql`, `001_schema.sql` e `002_push_subscriptions.sql` passaram. `python3 -m app.migrate` passou duas vezes. A consulta a `pg_enum` retornou `operator` e `viewer` para `userrole`.
2. Banco com esquema anterior: os scripts de inicialização usaram `001_schema.sql` do commit `08019f3`, que não continha os novos papéis. A migração atual passou e acrescentou ambos ao enum, confirmados por `pg_enum`.
3. A suíte local cobriu mapeamento OIDC, tenant obrigatório, lista, detalhe, ações e stream de incidentes, inclusive negação entre tenants e `viewer` sem escrita.

Os dois containers foram removidos após os ensaios. Ainda faltam UAT no Authentik real, MFA e recuperação, demais aplicações e aprovação do gate da Fase 1.
