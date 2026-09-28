# Phase 4 Dashboard Operational Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar a operação diária pelo aplicativo e dashboard do ness.OS com dados rastreáveis, estados de erro honestos e cobertura de todas as frentes implantadas.

**Architecture:** O backend publica um contrato agregado com payload, fonte, coleta, frescor e erro por domínio. O frontend exibe último valor conhecido somente com indicação explícita de obsolescência. Módulos ausentes são estados de produto documentados. A API da Contabo entra como fonte somente leitura de infraestrutura.

**Tech Stack:** React, TypeScript, Vite, FastAPI, PostgreSQL, Zabbix API, GLPI API, Contabo API e pytest/Vitest.

**Spec:** `docs/architecture/ness-os-official-architecture.md`.

## Global Constraints

- Gate de produção: Fases 0–3 aprovadas. Implementação e testes locais podem usar contratos das Fases 1–3 verificados antes do gate; deploy e aceite do dashboard aguardam aprovação.
- Remover dados demonstrativos e timestamps fixos das rotas usadas em produção.
- Não atualizar `last_success_at` quando uma coleta falhar.
- Respeitar tenant e papel em cada cartão, lista, busca, exportação e stream.

---

### Task 1: Definir o contrato de estado operacional

**Files:**
- Create: `app/backend/app/schemas/operational_status.py`
- Create: `app/backend/app/services/operational_status.py`
- Modify: `app/backend/app/api/routers/dashboard.py`
- Create: `app/backend/tests/test_operational_status.py`

**Interfaces:** Cada domínio retorna `{status, source, observed_at, last_success_at, freshness_seconds, stale, error_code, data}`; `status` é `ok`, `degraded`, `down`, `planned` ou `unavailable`.

- [ ] Criar testes de schema e transições para sucesso, timeout, valor anterior obsoleto, fonte ausente e módulo planejado.
- [ ] Executar `python -m pytest app/backend/tests/test_operational_status.py -q`; esperado: falha inicial.
- [ ] Implementar schema e serviço agregador sem alterar `last_success_at` em erro.
- [ ] Migrar a rota do dashboard para o contrato e repetir testes; esperado: aprovados.
- [ ] Commit: `git add app/backend/app/schemas/operational_status.py app/backend/app/services/operational_status.py app/backend/app/api/routers/dashboard.py app/backend/tests/test_operational_status.py && git commit -m "feat(dashboard): expose operational status contract"`.

### Task 2: Remover segurança estática e correlacionar versões

**Files:**
- Modify: `app/backend/app/api/routers/dashboard.py`
- Create: `app/backend/app/services/security_posture.py`
- Create: `app/backend/tests/test_security_posture.py`

**Interfaces:** Postura de segurança correlaciona software inventariado, versão instalada, vulnerabilidade, data da fonte e confiança; sem fonte configurada retorna `unavailable`, nunca uma lista fixa.

- [ ] Criar testes que rejeitem CVEs fixos, `updated_at` constante e vulnerabilidade sem versão instalada correlacionada.
- [ ] Executar o novo teste; esperado: falha inicial.
- [ ] Implementar adaptadores para o inventário disponível e deixar Wazuh como `planned` até a Fase 5.
- [ ] Repetir testes; esperado: dados reais ou estado indisponível explícito.
- [ ] Commit: `git add app/backend/app/api/routers/dashboard.py app/backend/app/services/security_posture.py app/backend/tests/test_security_posture.py && git commit -m "fix(security): replace static posture data with sourced status"`.

### Task 3: Corrigir comportamento de erro e frescor no frontend

**Files:**
- Modify: `app/frontend/src/components/CoreDashboard.tsx`
- Modify: `app/frontend/src/App.tsx`
- Modify: `app/frontend/package.json`
- Modify: `app/frontend/package-lock.json`
- Create: `app/frontend/src/components/CoreDashboard.test.tsx`

**Interfaces:** Falha preserva o último payload válido, mostra `Dados desatualizados`, horário da última coleta válida e ação de repetição; nunca mostra `fonte conectada` ou horário novo após erro.

- [ ] Criar testes para carregamento, sucesso, timeout, erro 401/403, dado obsoleto, retry e módulo planejado.
- [ ] Executar `npm test -- --run CoreDashboard` em `app/frontend`; esperado: falha inicial.
- [ ] Implementar o estado por domínio e acessibilidade de alertas e botões.
- [ ] Repetir teste, `npm run typecheck`, `npm run lint` e `npm run build`; esperado: todos aprovados.
- [ ] Commit: `git add app/frontend/src/components/CoreDashboard.tsx app/frontend/src/App.tsx app/frontend/package.json app/frontend/package-lock.json app/frontend/src/components/CoreDashboard.test.tsx && git commit -m "fix(ui): show accurate source freshness and failures"`.

### Task 4: Integrar inventário Contabo somente leitura

**Files:**
- Modify: `app/backend/app/api/routers/contabo.py`
- Create: `app/backend/app/services/contabo_inventory.py`
- Modify: `app/backend/tests/test_contabo_read_only_rbac.py`
- Create: `app/backend/tests/test_contabo_inventory.py`

**Interfaces:** Lista VPS, estado, região, recursos e identificador; reconcilia por identificadores explícitos com GLPI e Zabbix; API do Hub não expõe operações de criação, alteração ou exclusão.

- [ ] Criar testes de paginação, rate limit, timeout, cache, redaction, RBAC e ausência de métodos mutáveis.
- [ ] Executar os testes; esperado: falha inicial.
- [ ] Implementar cliente com timeout, backoff limitado e cache de curta duração.
- [ ] Adicionar reconciliação `Contabo VPS -> GLPI asset -> Zabbix host` com estados matched, missing e conflict.
- [ ] Repetir testes; esperado: aprovados.
- [ ] Executar contra a API real em modo leitura e registrar somente IDs não sensíveis, contagens e divergências.
- [ ] Commit: `git add app/backend/app/api/routers/contabo.py app/backend/app/services/contabo_inventory.py app/backend/tests/test_contabo_read_only_rbac.py app/backend/tests/test_contabo_inventory.py && git commit -m "feat(inventory): reconcile Contabo VPS read only"`.

### Task 5: Completar as jornadas operacionais do aplicativo

**Files:**
- Modify: `app/frontend/src/components/CoreDashboard.tsx`
- Create: `app/frontend/src/components/OperationalSources.tsx`
- Create: `app/frontend/src/components/BackupStatus.tsx`
- Create: `app/frontend/src/components/InfrastructureInventory.tsx`
- Create: `app/frontend/src/components/OperationalJourneys.test.tsx`
- Create: `docs/execution/gates/phase-4-dashboard-mvp.md`

**Interfaces:** O aplicativo cobre visão geral, fontes, incidentes, ativos/infraestrutura, tickets, backups e postura de segurança; cada área herda os estados do contrato operacional.

- [ ] Criar testes de jornada para operador e viewer de tenants distintos.
- [ ] Executar o teste; esperado: falha enquanto as áreas não estiverem disponíveis.
- [ ] Implementar navegação e componentes usando endpoints reais existentes e o contrato agregado.
- [ ] Exibir Wazuh como planejado antes da implantação e como fonte real somente após o gate da Fase 5.
- [ ] Validar teclado, foco, contraste, telas estreitas, vazios, erros e latência simulada.
- [ ] Executar testes, typecheck, lint e build; esperado: aprovados sem dados demo.
- [ ] Registrar o gate da Fase 4: dados rastreáveis, estados de erro/frescor e jornadas do MVP aprovados; Wazuh aparece como `planned` ou `unavailable`.
- [ ] Commit: `git add app/frontend/src/components/CoreDashboard.tsx app/frontend/src/components/OperationalSources.tsx app/frontend/src/components/BackupStatus.tsx app/frontend/src/components/InfrastructureInventory.tsx app/frontend/src/components/OperationalJourneys.test.tsx docs/execution/gates/phase-4-dashboard-mvp.md && git commit -m "feat(ui): complete ness.OS operational journeys"`.

### Task 6 (pós-MVP): Dimensionar e aprovar a contratação do Wazuh

Esta tarefa não integra o gate de saída da Fase 4 para o MVP. Executá-la somente após o aceite do MVP; compra e rollout exigem aprovação explícita de capacidade e custo.

**Files:**
- Create: `docs/execution/wazuh-capacity-and-cost-decision.md`
- Create: `docs/execution/gates/wazuh-capacity-and-purchase.md`

- [ ] Medir volume de eventos dos 5 endpoints piloto, retenção desejada, crescimento e custo mensal de VPS, snapshots e Object Storage.
- [ ] Comparar a medição com o baseline do desenho: nó dedicado, 8 vCPU, 8 GiB RAM e pelo menos 100 GB para 25–50 endpoints e 90 dias.
- [ ] Registrar cotação Contabo, limite de orçamento, região, RPO/RTO e custo de saída.
- [ ] Usar o gate da Fase 4 já aprovado como entrada; confirmar que a decisão sobre Wazuh não altera o estado das fontes do MVP.
- [ ] Confirmar que comprar, adiar ou redimensionar não degrada as frentes já operacionais.
- [ ] Obter aprovação explícita do orçamento antes de criar a VPS.
- [ ] Registrar a decisão pós-MVP e commit: `git add docs/execution/wazuh-capacity-and-cost-decision.md docs/execution/gates/wazuh-capacity-and-purchase.md && git commit -m "docs(gate): decide Wazuh capacity and purchase"`.
