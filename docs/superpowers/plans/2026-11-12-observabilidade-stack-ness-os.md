# Plano de implementação — Observabilidade da stack ness.OS

> Execução incremental, sem mutações de infraestrutura no provedor.

**Objetivo:** consolidar control plane (Contabo) + data plane (runtime/fonte) em uma visão operacional única para decisão diária.

**Spec:** `docs/superpowers/specs/2026-11-12-observabilidade-stack-ness-os-design.md`

## Restrições globais

- Manter Contabo em read-only.
- Reusar contratos já existentes (`OperationalStatus`) antes de criar novos.
- Não alterar comportamento de tenant/RBAC fora do necessário.
- Sem deploy em produção fora do processo de gate.

---

## Task 1 — Serviço agregador de stack health

**Files:**
- Create: `app/backend/app/services/stack_health.py`
- Create: `app/backend/tests/test_stack_health.py`

**Entrega:** função agregadora que combina:
- `/api/dashboard/sources` (Zabbix/GLPI/Atera/Wazuh planned),
- client Contabo read-only (`compute`, `snapshots`, `networks`, `firewalls`),
- estado de runtime/pipeline já disponível.

- [ ] Criar testes para consolidação de estado (`ok`, `degraded`, `down`) por stack.
- [ ] Cobrir caso: VPS `running` + fonte crítica `down` => stack `degraded/down`.
- [ ] Cobrir caso stale sem perda de último sucesso.
- [ ] Implementar agregador com timeout por fonte e erro redigido.
- [ ] Executar `python -m pytest app/backend/tests/test_stack_health.py -q`.

## Task 2 — Endpoint operacional consolidado

**Files:**
- Modify: `app/backend/app/api/routers/dashboard.py`
- Create: `app/backend/tests/test_stack_health_router.py`

**Entrega:** `GET /api/ops/stack-health` com `require_noc`.

- [ ] Adicionar rota com payload `{summary, stacks, domains, findings}`.
- [ ] Garantir erros 502 sem vazamento de detalhes de provedor.
- [ ] Testar autorização (noc permitido; sem papel => 401/403).
- [ ] Executar `python -m pytest app/backend/tests/test_stack_health_router.py -q`.

## Task 3 — Visão no frontend (MVP enxuto)

**Files:**
- Create: `app/frontend/src/components/StackHealthPanel.tsx`
- Modify: `app/frontend/src/components/CoreDashboard.tsx`
- Create: `app/frontend/src/components/StackHealthPanel.test.tsx`

**Entrega:** painel curto por stack com estado, causa e frescor.

- [ ] Exibir stacks críticas (`aiops`, `zabbix-prod`, `zabbix-prd-01`) com semáforo.
- [ ] Exibir badge de stale e última coleta válida.
- [ ] Exibir finding principal por stack (ex.: backup vencido, runtime down).
- [ ] Testar loading, erro, stale e sucesso.
- [ ] Executar `npm test -- --run StackHealthPanel`, `npm run typecheck`, `npm run build`.

## Task 4 — Regras de alerta operacional (sem automação destrutiva)

**Files:**
- Create: `docs/runbooks/stack-health-alert-rules.md`
- Modify: `infra/scripts/hub-health-history.py` (somente se necessário para métrica de frescor)
- Create: `infra/tests/test-stack-health-alert-rules.sh` (se houver script)

**Entrega:** regras operacionais documentadas e verificáveis.

- [ ] Definir alerta para `stack down > 5 min`.
- [ ] Definir alerta para `snapshot_age > limiar`.
- [ ] Definir alerta para `runtime down + vps running`.
- [ ] Registrar owner e ação esperada por alerta.

## Task 5 — Evidência e gate operacional

**Files:**
- Create: `docs/execution/evidence/stack-health-baseline-2026-11-12.md`
- Create: `docs/execution/gates/stack-observability-v1.md`

**Entrega:** baseline reproduzível e critério de aceite da V1.

- [ ] Capturar baseline real das 3 VPS Contabo com IDs e estado.
- [ ] Capturar payload do endpoint consolidado com timestamps e frescor.
- [ ] Validar pelo menos 1 cenário degradado controlado (fonte indisponível simulada).
- [ ] Registrar resultado no gate (`PASS`/`FAIL` + pendências).

---

## Ordem recomendada

1. Task 1
2. Task 2
3. Task 3
4. Task 5
5. Task 4 (pode rodar junto da 5 se já houver sinais suficientes)

## Stop condition (evitar overbuild)

Parar em V1 quando:
- endpoint consolidado existir,
- painel mostrar estado por stack com causa e frescor,
- gate V1 estiver com evidência mínima.

Qualquer item além disso (FinOps completo, automação de remediação, ações na Contabo) vira fase nova.
