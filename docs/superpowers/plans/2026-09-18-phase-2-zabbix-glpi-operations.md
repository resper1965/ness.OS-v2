# Phase 2 Zabbix and GLPI Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar inventário, monitoração e gestão de tickets confiáveis e provar o fluxo idempotente de alerta a resolução.

**Architecture:** Zabbix permanece fonte de telemetria e eventos, GLPI permanece fonte de ativos e tickets e o Hub mantém o vínculo entre evento, incidente e ticket. O saneamento ocorre em ondas pequenas, via API oficial, com snapshots antes de cada escrita.

**Tech Stack:** Zabbix 7.0 API, GLPI API, Python, Bash, FastAPI, Celery e PostgreSQL.

**Spec:** `docs/architecture/ness-os-official-architecture.md`.

## Global Constraints

- Gate de produção: Fase 0 aprovada. Baselines, implementação e testes locais podem avançar; escrita ou rollout em Zabbix/GLPI de produção fica bloqueado até o gate passar.
- Não editar tabelas do Zabbix ou GLPI diretamente.
- Não tentar eliminar todos os alertas históricos para aprovar a fase; classificar, atribuir e reduzir o conjunto operacional prioritário.

---

### Task 1: Produzir baseline reproduzível de qualidade

**Files:**
- Modify: `infra/scripts/zabbix-offline-polish-report.sh`
- Modify: `infra/scripts/zabbix-security-state-report.sh`
- Modify: `infra/scripts/glpi-inventory-readiness-report.sh`
- Create: `infra/tests/test-source-quality-reports.sh`
- Create: `docs/execution/evidence/phase-2-source-baseline.md`

**Interfaces:** Relatórios JSON incluem horário UTC, versão, escopo, totais e IDs técnicos necessários à correção; saída não contém credenciais.

- [ ] Adicionar em `test-source-quality-reports.sh` testes de contrato para os campos do relatório e redaction de segredos.
- [ ] Executar os relatórios em modo somente leitura e capturar: hosts ativos, itens não suportados, triggers desconhecidas, hosts sem tags/template, problemas ativos, entidades, categorias e cobertura de inventário.
- [ ] Classificar cada achado por tenant, criticidade, causa e ação; separar ruído histórico de falhas correntes.
- [ ] Fixar os números de entrada na evidência sem copiar dados pessoais desnecessários.
- [ ] Commit: `git add infra/scripts/zabbix-offline-polish-report.sh infra/scripts/zabbix-security-state-report.sh infra/scripts/glpi-inventory-readiness-report.sh infra/tests/test-source-quality-reports.sh docs/execution/evidence/phase-2-source-baseline.md && git commit -m "feat(ops): baseline Zabbix and GLPI source quality"`.

### Task 2: Sanear o piloto prioritário do Zabbix

**Files:**
- Modify: `infra/scripts/zabbix-cavan-inventory-report.sh`
- Create: `infra/scripts/zabbix-quality-wave.py`
- Create: `infra/tests/test-zabbix-quality-wave.py`
- Create: `docs/runbooks/zabbix-quality-waves.md`

**Interfaces:** `zabbix-quality-wave.py plan` gera plano sem escrita; `apply --plan <file>` aceita somente alterações previamente calculadas e `rollback --evidence <file>` reverte tags/templates alterados pela onda.

- [ ] Escrever testes para dry-run, precondição divergente, idempotência, limite de lote e rollback.
- [ ] Executar `python -m pytest infra/tests/test-zabbix-quality-wave.py -q`; esperado: falha inicial.
- [ ] Implementar cliente API com limite padrão de 10 hosts e comparação do estado antes de cada escrita.
- [ ] Repetir testes; esperado: aprovados.
- [ ] Selecionar 5 hosts críticos, garantir tenant, tags, template e ownership e corrigir itens não suportados conhecidos.
- [ ] Observar por 24 horas; ampliar para 25 e depois para o restante apenas se não houver regressão.
- [ ] Medir redução por categoria e manter exceções justificadas no runbook.
- [ ] Commit: `git add infra/scripts/zabbix-cavan-inventory-report.sh infra/scripts/zabbix-quality-wave.py infra/tests/test-zabbix-quality-wave.py docs/runbooks/zabbix-quality-waves.md && git commit -m "feat(zabbix): add controlled quality remediation waves"`.

### Task 3: Consolidar catálogo e vínculo de ativos do GLPI

**Files:**
- Modify: `infra/scripts/glpi-cavan-inventory-report.sh`
- Modify: `infra/scripts/glpi-hub-integrity-check.py`
- Modify: `infra/scripts/hub-glpi-integrity-check.py`
- Create: `infra/tests/test-glpi-integrity.py`
- Create: `docs/operations/glpi-service-catalog.md`

**Interfaces:** Cada ativo operacional tem entidade, tenant, identificador externo estável e vínculo opcional ao `hostid` do Zabbix; categorias usadas pelo Hub possuem IDs resolvidos pela API.

- [ ] Criar fixtures para ativo ausente, duplicado, tenant divergente e categoria inválida.
- [ ] Executar os testes de integridade existentes; esperado: novos casos falham.
- [ ] Implementar reconciliação somente leitura e uma saída de correção separada.
- [ ] Definir categorias, prioridades, grupos de atribuição e estados aceitos no catálogo.
- [ ] Aplicar um lote piloto após dry-run e repetir a reconciliação; esperado: nenhuma duplicidade e vínculos estáveis.
- [ ] Commit: `git add infra/scripts/glpi-cavan-inventory-report.sh infra/scripts/glpi-hub-integrity-check.py infra/scripts/hub-glpi-integrity-check.py infra/tests/test-glpi-integrity.py docs/operations/glpi-service-catalog.md && git commit -m "feat(glpi): reconcile assets and service catalog"`.

### Task 4: Provar alerta, incidente, ticket e resolução

**Files:**
- Modify: `app/backend/app/workers/alert_tasks.py`
- Modify: `app/backend/app/services/triage_engine.py`
- Modify: `app/backend/tests/test_alert_glpi_idempotency.py`
- Modify: `app/backend/tests/test_glpi_readiness.py`
- Modify: `infra/scripts/hub-integration-monitor.sh`
- Create: `docs/execution/evidence/phase-2-alert-ticket-e2e.md`

**Interfaces:** Um `source_event_id` gera no máximo um incidente e um ticket GLPI; replays atualizam o registro existente; recuperação fecha ou resolve conforme a política documentada.

- [ ] Criar testes para entrega inicial, três replays, erro transitório, retry e evento de recuperação.
- [ ] Executar os testes; esperado: falha nos comportamentos ausentes.
- [ ] Ajustar apenas o código necessário ao contrato e repetir; esperado: aprovado.
- [ ] Com notificações externas desligadas, gerar um alerta sintético nomeado e rastreável em host piloto.
- [ ] Confirmar um incidente, um ticket, IDs cruzados, timestamps coerentes e resolução propagada.
- [ ] Reenviar o mesmo evento e confirmar que as contagens permanecem em um.
- [ ] Registrar evidência e remover o artefato sintético pela API.
- [ ] Commit: `git add app/backend/app/workers/alert_tasks.py app/backend/app/services/triage_engine.py app/backend/tests/test_alert_glpi_idempotency.py app/backend/tests/test_glpi_readiness.py infra/scripts/hub-integration-monitor.sh docs/execution/evidence/phase-2-alert-ticket-e2e.md && git commit -m "test(ops): prove idempotent alert to ticket lifecycle"`.

### Task 5: Aprovar o gate da Fase 2

**Files:**
- Create: `docs/execution/gates/phase-2-zabbix-glpi.md`

- [ ] Confirmar proteção por backup e rollback antes de cada onda.
- [ ] Confirmar 100% dos hosts do piloto com tenant, tags, template e vínculo de inventário.
- [ ] Confirmar itens não suportados e triggers desconhecidas do piloto classificados ou corrigidos.
- [ ] Confirmar teste ponta a ponta e replay sem duplicação.
- [ ] Executar testes e relatórios desta fase; esperado: código zero e relatórios atuais.
- [ ] Registrar o gate e commit: `git add docs/execution/gates/phase-2-zabbix-glpi.md && git commit -m "docs(gate): approve monitoring and service operations"`.
