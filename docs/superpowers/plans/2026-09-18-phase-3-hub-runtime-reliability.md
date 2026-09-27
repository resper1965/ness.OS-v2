# Phase 3 Hub Runtime Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a saúde do Hub refletir os componentes reais, endurecer processamento assíncrono e implantar releases reproduzíveis com rollback comprovado.

**Architecture:** API, workers, PostgreSQL e Redis publicam sinais independentes. O agregador calcula disponibilidade, backlog, idade e erro sem mascarar falhas. Processamento assíncrono usa identidade estável, lock com expiração e estado durável para suportar retry e replay.

**Tech Stack:** FastAPI, Celery, Redis, PostgreSQL, Docker Compose, pytest, Ruff, Black e MyPy.

**Spec:** `docs/architecture/ness-os-official-architecture.md`.

## Global Constraints

- Gate de produção: Fase 0 aprovada. Desenvolvimento e testes locais podem avançar; deploy da Fase 3 continua bloqueado até o gate passar.
- Uma sonda não pode usar `|| exit 0`, aceitar resposta vazia ou consultar banco Redis diferente do broker observado.
- Rollout canário deve preservar o serviço anterior até as sondas passarem.

---

### Task 1: Corrigir o contrato de saúde das filas

**Files:**
- Modify: `app/backend/app/integrations/pipeline_health.py`
- Modify: `app/backend/app/workers/celery_app.py`
- Modify: `app/backend/tests/test_pipeline_health.py`

**Interfaces:** Saúde de fila informa `queue`, `redis_db`, `depth`, `oldest_age_seconds`, `workers_seen`, `status`, `checked_at` e `error`; conexão deriva do broker Celery efetivo.

- [x] Criar teste com broker em DB 1 e Redis genérico em DB 0; confirmar que a implementação atual lê o banco errado.
- [x] Criar testes para fila vazia, backlog crescente, Redis indisponível e worker ausente, incluindo idade da mensagem e timestamp ausente.
- [x] Executar `python -m pytest tests/test_pipeline_health.py -q` em `app/backend`; os novos casos falharam antes da correção, depois 16 passaram.
- [x] Derivar o cliente da conexão de leitura efetiva do Celery, separar a telemetria no Redis próprio e calcular estado sem converter exceção em fila vazia.
- [x] Repetir o teste; todos os 16 casos passaram. Ruff check e format também passaram.
- [x] Commit: `git add app/backend/app/integrations/pipeline_health.py app/backend/app/workers/celery_app.py app/backend/tests/test_pipeline_health.py docs/superpowers/plans/2026-09-18-phase-3-hub-runtime-reliability.md && git commit -m "fix(health): inspect the effective Celery broker queues"`.

### Task 2: Tornar healthchecks de containers fail-closed

**Files:**
- Modify: `docker-compose.yml`
- Modify: `infra/scripts/aiops-runtime-readiness.sh`
- Modify: `infra/tests/test-aiops-runtime-readiness.sh`

**Interfaces:** API e workers ficam `unhealthy` quando o processo, broker, banco ou heartbeat obrigatório falha; startup grace period evita falso negativo durante migração.

- [ ] Criar teste estático que rejeite healthchecks terminados por `|| exit 0` e teste funcional com worker interrompido.
- [ ] Executar `bash infra/tests/test-aiops-runtime-readiness.sh`; esperado: falha inicial.
- [ ] Substituir as sondas por comandos que validem processo, dependências e heartbeat com timeout.
- [ ] Repetir o teste e interromper um worker em ambiente de teste; esperado: container fica unhealthy e readiness retorna código não zero.
- [ ] Restaurar o worker e confirmar recuperação sem reiniciar serviços não relacionados.
- [ ] Commit: `git add docker-compose.yml infra/scripts/aiops-runtime-readiness.sh infra/tests/test-aiops-runtime-readiness.sh && git commit -m "fix(runtime): make worker health checks fail closed"`.

### Task 3: Endurecer idempotência e concorrência

**Files:**
- Modify: `app/backend/app/services/triage_engine.py`
- Modify: `app/backend/app/workers/alert_tasks.py`
- Modify: `app/backend/tests/test_alert_glpi_idempotency.py`
- Create: `app/backend/tests/test_alert_task_concurrency.py`

**Interfaces:** Chave idempotente é `(tenant_id, source, source_event_id)` com restrição durável; lock possui owner token e TTL; somente o owner libera; retry não perde o vínculo com incidente/ticket.

- [ ] Criar testes concorrentes com duas tarefas, expiração do lock, crash depois do incidente e antes do ticket e replay após restart.
- [ ] Executar os testes; esperado: ao menos um caso demonstra duplicação ou estado inconsistente.
- [ ] Implementar restrição/transação e lock com compare-and-delete conforme o armazenamento existente.
- [ ] Repetir os testes 20 vezes para expor corrida; esperado: um incidente e um ticket em todas as execuções.
- [ ] Commit: `git add app/backend/app/services/triage_engine.py app/backend/app/workers/alert_tasks.py app/backend/tests/test_alert_glpi_idempotency.py app/backend/tests/test_alert_task_concurrency.py && git commit -m "fix(pipeline): make alert processing durable and idempotent"`.

### Task 4: Automatizar deploy por manifesto e rollback

**Files:**
- Modify: `infra/scripts/aiops-runtime-preflight.sh`
- Create: `infra/scripts/ness-deploy-release.sh`
- Create: `infra/tests/test-ness-deploy-release.sh`
- Modify: `docs/runbooks/release-and-rollback.md`

**Interfaces:** `ness-deploy-release.sh --manifest <json> --canary` valida backup, digests, configurações, migrações e saúde; `--rollback <release-id>` restaura imagens e configuração anterior e executa sondas.

- [ ] Escrever testes para manifesto divergente, backup vencido, migração incompatível, canário falho e rollback aprovado.
- [ ] Executar `bash infra/tests/test-ness-deploy-release.sh`; esperado: falha inicial.
- [ ] Implementar fases preflight, pull por digest, migração, canário, promoção e rollback com journal estruturado.
- [ ] Repetir testes; esperado: aprovados.
- [ ] Fazer deploy canário de uma release sem alteração funcional, provocar falha de sonda e comprovar rollback.
- [ ] Repetir com sondas aprovadas e comprovar que o manifesto remoto coincide com a release.
- [ ] Commit: `git add infra/scripts/aiops-runtime-preflight.sh infra/scripts/ness-deploy-release.sh infra/tests/test-ness-deploy-release.sh docs/runbooks/release-and-rollback.md && git commit -m "feat(release): automate canary deploy and rollback"`.

### Task 5: Observar estabilidade e aprovar o gate

**Files:**
- Modify: `infra/scripts/hub-health-history.py`
- Modify: `infra/tests/test-hub-health-history.py`
- Create: `docs/execution/gates/phase-3-hub-runtime.md`

- [ ] Adicionar métricas de disponibilidade, backlog máximo, idade do item mais antigo, retries, falhas, incidentes sem ticket e divergência de release.
- [ ] Executar `python -m pytest infra/tests/test-hub-health-history.py -q`; esperado: aprovado.
- [ ] Observar por sete dias com zero divergência de release, zero duplicação e nenhuma falha silenciosa de worker.
- [ ] Exigir backlog retornando ao normal após teste de carga controlado e alertas acionáveis para fontes indisponíveis.
- [ ] Executar `python -m pytest app/backend/tests -q`, Ruff, Black check e MyPy; esperado: todos aprovados.
- [ ] Registrar o gate e commit: `git add infra/scripts/hub-health-history.py infra/tests/test-hub-health-history.py docs/execution/gates/phase-3-hub-runtime.md && git commit -m "docs(gate): approve Hub runtime reliability"`.
