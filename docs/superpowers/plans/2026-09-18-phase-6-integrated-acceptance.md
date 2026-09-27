# Phase 6 Integrated Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provar a operação completa do ness.OS, incluindo aplicativo, fontes implantadas, resposta a incidentes, recuperação e sustentação por sete dias.

**Architecture:** O aceite percorre as interfaces públicas e os fluxos operacionais reais. Evidências são produzidas pelos mesmos scripts, APIs e dashboards usados pela operação. Falha em um gate retorna ao plano dono do componente.

**Tech Stack:** Toda a stack do ness.OS, scripts de readiness, pytest, testes frontend, systemd, Docker Compose e Restic.

**Spec:** `docs/architecture/ness-os-official-architecture.md` e todos os gates das Fases 0–5.

## Global Constraints

- Gates de produção/aceite: Fases 0–4 aprovadas; Fase 5 aprovada se o Wazuh tiver sido contratado. Preparação e testes locais podem ocorrer antes; UAT de produção e aceite final não podem.
- Wazuh adiado deve aparecer como `planned` e não bloqueia aceite do escopo contratado.
- Não executar exercício destrutivo sem snapshot atual e rollback comprovado.

---

### Task 1: Consolidar runbooks e ownership

**Files:**
- Create: `docs/runbooks/ness-os-operations-index.md`
- Create: `docs/operations/service-ownership.md`
- Create: `docs/operations/escalation-matrix.md`

**Interfaces:** Cada serviço possui owner, substituto, SLO, sinais, dependências, procedimento de incidente, recuperação, escalonamento e link de dashboard.

- [ ] Indexar runbooks de Hub, Zabbix, GLPI, Authentik, Psono, n8n, Contabo, backup e Wazuh quando implantado.
- [ ] Definir severidades, tempo de reconhecimento, canais e autoridade para rollback e break-glass.
- [ ] Fazer um operador que não escreveu o runbook executar uma sonda e um rollback simulado.
- [ ] Corrigir passos ambíguos revelados pelo exercício.
- [ ] Commit: `git add docs/runbooks/ness-os-operations-index.md docs/operations/service-ownership.md docs/operations/escalation-matrix.md && git commit -m "docs(ops): consolidate ownership and runbooks"`.

### Task 2: Executar UAT por persona e tenant

**Files:**
- Create: `docs/execution/uat/ness-os-persona-matrix.md`
- Create: `docs/execution/evidence/phase-6-application-uat.md`

**Interfaces:** Personas `admin`, `operator` e `viewer` executam login, dashboard, fontes, incidente, ativo, ticket, backup e logout nos tenants permitidos e proibidos.

- [ ] Preparar dois tenants e dados sintéticos identificáveis, sem dados pessoais reais.
- [ ] Executar cada jornada no aplicativo em desktop e viewport móvel.
- [ ] Confirmar escrita somente para papéis autorizados e nenhuma enumeração entre tenants.
- [ ] Confirmar estados de erro desligando uma fonte de teste e verificando frescor e recuperação.
- [ ] Registrar captura textual, horário, release e resultado por célula.
- [ ] Commit: `git add docs/execution/uat/ness-os-persona-matrix.md docs/execution/evidence/phase-6-application-uat.md && git commit -m "test(acceptance): complete persona and tenant UAT"`.

### Task 3: Executar exercício operacional ponta a ponta

**Files:**
- Create: `docs/execution/evidence/phase-6-incident-drill.md`
- Modify: `infra/scripts/hub-integration-monitor.sh`

**Interfaces:** Exercício cria sinal sintético, incidente, ticket, atribuição, reconhecimento, recuperação e encerramento; com Wazuh implantado, inclui um evento de segurança inofensivo do piloto.

- [ ] Registrar baseline de contagens antes do exercício.
- [ ] Gerar alerta Zabbix sintético e confirmar ingestão no limite de latência definido.
- [ ] Confirmar criação única do incidente e ticket GLPI, atribuição correta e visibilidade no dashboard.
- [ ] Repetir o evento e confirmar idempotência.
- [ ] Gerar recuperação, confirmar encerramento e comparar contagens finais.
- [ ] Se Wazuh estiver implantado, repetir o ciclo com evento inofensivo e confirmar normalização pelo adapter versionado.
- [ ] Commit: `git add docs/execution/evidence/phase-6-incident-drill.md infra/scripts/hub-integration-monitor.sh && git commit -m "test(acceptance): run integrated incident drill"`.

### Task 4: Executar exercício de desastre e restauração

**Files:**
- Create: `docs/execution/evidence/phase-6-disaster-recovery.md`
- Modify: `docs/runbooks/ness-os-operations-index.md`

**Interfaces:** Restauração isolada usa os snapshots externos mais recentes, mede RPO/RTO e valida integridade sem apontar tráfego público ao ambiente restaurado.

- [ ] Selecionar snapshots do Hub, Zabbix, Psono e Wazuh quando implantado, todos com idade inferior a 24 horas.
- [ ] Restaurar bancos, configurações e metadados em rede isolada.
- [ ] Validar autenticação local técnica, contagens, vínculos e checksums.
- [ ] Medir RPO e RTO por componente e comparar com o objetivo aprovado.
- [ ] Destruir somente os recursos temporários cujos caminhos e identificadores foram registrados e conferidos.
- [ ] Atualizar runbooks com diferenças observadas.
- [ ] Commit: `git add docs/execution/evidence/phase-6-disaster-recovery.md docs/runbooks/ness-os-operations-index.md && git commit -m "test(recovery): complete integrated disaster exercise"`.

### Task 5: Observar sete dias e aprovar produção

**Files:**
- Create: `docs/execution/evidence/phase-6-seven-day-observation.md`
- Create: `docs/execution/gates/phase-6-production-acceptance.md`
- Modify: `docs/execution/project-stage-2026-09-17.md`

- [ ] Congelar mudanças não urgentes durante a janela de observação.
- [ ] Registrar diariamente disponibilidade, fontes, backlog, idade, falhas, retries, duplicações, tickets órfãos, backups e restauração mais recente.
- [ ] Exigir zero incidente crítico sem owner, zero backup vencido, zero divergência de release e zero vazamento entre tenants.
- [ ] Classificar problemas não críticos com owner e prazo; não registrar `PASS` para critério sem evidência.
- [ ] Executar a suíte backend, frontend, infraestrutura, prechecks públicos e verificações de manifesto; esperado: todos aprovados.
- [ ] Atualizar o estágio do projeto com estado real de cada módulo: `operational`, `degraded`, `planned` ou `unavailable`.
- [ ] Registrar aceite final, release, riscos residuais e decisão sobre Wazuh.
- [ ] Commit: `git add docs/execution/evidence/phase-6-seven-day-observation.md docs/execution/gates/phase-6-production-acceptance.md docs/execution/project-stage-2026-09-17.md && git commit -m "docs(gate): accept ness.OS production operation"`.
