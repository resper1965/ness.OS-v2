# Hub — readiness em containers locais (2026-09-28)

**Escopo:** imagem do backend construída do código atual e containers descartáveis na rede `ness-local-ready-20260928` do Docker Desktop. PostgreSQL e Redis usaram os digests fixados em `app/docker-compose.yml`; o banco recebeu `000_init.sql`, `001_schema.sql` e `002_push_subscriptions.sql`. Nenhum serviço de produção foi alterado.

| Ensaio | Resultado |
|---|---|
| API com PostgreSQL e Redis disponíveis | `GET /ready` → `200` |
| Redis parado | `GET /ready` → `503` |
| Redis reiniciado | `GET /ready` → `200` |
| Worker de alertas ativo | `celery inspect ping -d alerts@$(hostname)` → `pong` |
| Worker de ML ativo | `celery inspect ping -d ml@$(hostname)` → `pong` |
| Worker de ML parado com worker de alertas ativo | Consulta ao destino exato de ML não retornou `pong` |

A sonda anterior do Compose, com destino `alerts@*`, falhou enquanto o worker de alertas estava ativo e respondia à consulta sem destino. O destino exato baseado no hostname do container passou. O teste `infra/tests/test-aiops-runtime-readiness.sh` passou após a correção. Todos os containers e a rede de ensaio foram removidos.

Este ensaio valida a imagem e as sondas locais. Ainda faltam a execução do Compose completo no ambiente alvo, as integrações reais e a aprovação dos gates de release.
