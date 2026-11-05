# Dados por cliente editáveis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tudo que varia por cliente deixa de ser constante em código e passa a ser dado editável (por API, e depois pela tela de contratos), com histórico de mudança.

**Architecture:** O **contrato** (`n_infraops_contracts`, em construção na branch `feat/sla-politica-editavel`) é o centro: um cliente tem um contrato; o contrato carrega modalidade, SLA, calendário, escalonamento e a política de atendimento. O cadastro do **cliente** (`n_infraops_customers`) guarda identidade e mapeamentos (entidade GLPI, apelidos). Nada de valor por cliente fica em `.py`; o que não está cadastrado cai em um padrão interno marcado como não contratual, nunca em valor embutido.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL, migração idempotente em `app/migrate.py` + `sql/001_schema.sql` (paridade testada), pytest.

**Spec:** `docs/specs/contratos-sla-editaveis.md` (vem com a branch `feat/sla-politica-editavel`), `docs/specs/soc-attendance-policy.md`, `docs/operations/glpi-t08-diagnostico.md`.

## Global Constraints

- Esta tarefa depende do PR `feat/sla-politica-editavel` (contratos, políticas, calendários, passos) já na `main`. Não recriar essas tabelas.
- Fuso: `America/Sao_Paulo` (decisão do Ricardo, 05/11).
- Nenhum valor contratual é inventado: o que não vem de contrato carrega `contractual=false`.
- Edição só por `admin`/`platform_admin`; leitura por `operator`+; cliente/viewer recebem 403.
- Toda alteração em dado de contrato grava `n_infraops_contract_changes` (antes/depois).
- Cada migração é aditiva e idempotente; seed com `ON CONFLICT DO NOTHING`; paridade `migrate.py` × `001_schema.sql` testada em `test_bootstrap_sql.py`.
- Segredos e dados pessoais de contato nunca em seed nem em log.
- Sem tela nesta fase (espera o redesenho). Sem deploy sem a frase do Ricardo.
- Comportamento atual com os valores semeados deve permanecer idêntico (suíte existente verde).

## Inventário: o que varia por cliente e onde está hoje

| # | Dado | Hoje | Destino |
|---|---|---|---|
| 1 | Nome do cliente → entidade GLPI (13 nomes e apelidos) | `resolve_glpi_entity_id` em `workers/alerts.py:66` | `n_infraops_customers` + `n_infraops_customer_aliases` (Task 1) |
| 2 | Regra "grupo de hosts `[Cliente]` → cliente", exceções "Ness", par Alupar/Alupar-PE/CO | `customer_from_hostgroups` em `workers/alerts.py:164` | alias e flag `ignore_when_with` no cadastro (Task 2) |
| 3 | Modalidade (managed/onsite/shared) | `n_infraops_tenant_mappings.modality`, por SQL | contrato é a fonte; mapeamento deriva (Task 3) |
| 4 | Prazos, calendário, feriados, escalonamento | `notifications.py` (constantes) | tabelas do PR de contratos |
| 5 | Piso de atendimento SOC (nível 12), limiar de score (75), janela 24 h OT, janela de amostra semanal | constantes em `secops.py`, `triage_engine.py` | `n_infraops_contract_policy_params` (Task 4) |
| 6 | Frescor e cobertura por fonte (900 s, 300 s) | `pipeline_health.py:24-29` | parâmetro por contrato, padrão global (Task 4) |
| 7 | Contatos de aviso do cliente (e-mail/telefone de plantão do cliente) | não existe | `n_infraops_customer_contacts` (Task 5) |
| 8 | Lista de clientes afetados nos cards do SecOps | strings fixas em `secops.py:41-185` (dado de exemplo/mock) | fora de escopo: é conteúdo de demonstração; remover quando a tela real existir |

## Review Focus

- Cliente com apelido não cadastrado: deve recusar o ticket (`ValueError`), nunca cair em entidade 0.
- Dois clientes com o mesmo apelido: cadastro recusa (409); resolução ambígua não escolhe um.
- Contrato `ended` ou fora da vigência: tratado como inexistente, cai no padrão não contratual.
- Edição de parâmetro vale no ciclo seguinte, sem reiniciar worker.
- Alteração sem usuário autenticado ou por papel sem direito: 403 e nada gravado.

---

### Task 1: Cadastro de clientes e apelidos (substitui `resolve_glpi_entity_id`)

**Files:**
- Modify: `app/backend/app/models/models.py`, `app/backend/app/migrate.py`, `app/backend/sql/001_schema.sql`, `app/backend/app/workers/alerts.py:66-97`
- Create: `app/backend/app/services/customers.py`, `app/backend/app/api/routers/customers.py`
- Test: `app/backend/tests/test_customers.py`, `app/backend/tests/test_bootstrap_sql.py`

**Interfaces:**
- Consumes: modelo de contrato (PR `feat/sla-politica-editavel`).
- Produces:
  - tabela `n_infraops_customers(id, key UNIQUE, display_name, glpi_entity_id INT NULL, active bool, created_at, updated_at, updated_by_user_id)`;
  - tabela `n_infraops_customer_aliases(customer_id FK, alias_norm TEXT UNIQUE)`, `alias_norm` = `lower().strip()`;
  - `async def resolve_customer(session, name: str) -> Customer | None` em `services/customers.py`;
  - `async def resolve_glpi_entity_id(session, customer_name: str) -> int` (mesma assinatura semântica, agora assíncrona; levanta `ValueError("Cliente sem entidade GLPI mapeada; ticket recusado")` se não houver cliente ativo com `glpi_entity_id`).

- [ ] **Step 1: Write the failing tests** em `test_customers.py`: `test_seed_matches_legacy_mapping` (os 13 nomes/apelidos do `resolve_glpi_entity_id` atual resolvem para os mesmos ids: Alupar=1, TBE=2, Target=3, LTB=4, Alupar PE=5, Alupar CO=6, Bichara=7, Cavan=8, Nova Energia=9, Numen=10, TNE=11, Unimed=12, Ness=0); `test_unknown_alias_refused` (nome fora do cadastro → `ValueError`, nunca entidade 0); `test_duplicate_alias_409` (API); `test_inactive_customer_refused`; `test_edit_alias_effective_next_call` (alias novo resolve sem reiniciar); `test_only_admin_edits` (operator/cliente 403).
- [ ] **Step 2: Run** `pytest tests/test_customers.py -q` — Expected: FAIL (módulo não existe).
- [ ] **Step 3: Implement** modelo, migração e seed idempotente com os valores do código atual (única vez em que eles aparecem fora de teste); `resolve_glpi_entity_id` em `alerts.py` passa a chamar `services.customers` e a função antiga é removida junto com os chamadores ajustados (`customer_from_hostgroups` recebe o resolvedor por parâmetro ou fica assíncrono, o que for menor diff).
- [ ] **Step 4: Implement API** `GET/POST/PUT /api/customers` e `POST/DELETE /api/customers/{id}/aliases`: 409 em alias duplicado, 422 em nome vazio, auditoria em `n_infraops_contract_changes` (entity=`customer`).
- [ ] **Step 5: Run** suíte completa — Expected: PASS, incluindo `test_alert_glpi_idempotency.py` sem mudança de comportamento.
- [ ] **Step 6: Mutation:** fazer `resolve_glpi_entity_id` devolver 0 para desconhecido e provar que `test_unknown_alias_refused` falha; reverter.
- [ ] **Step 7: Commit** `feat: cadastro de clientes e apelidos editáveis`.

### Task 2: Regra de grupo de hosts (`[Cliente]`) como dado

**Files:**
- Modify: `app/backend/app/workers/alerts.py:164-185`, models/migrate/schema
- Test: `app/backend/tests/test_customers.py`

**Interfaces:**
- Consumes: `resolve_customer` da Task 1.
- Produces: tabela `n_infraops_hostgroup_rules(id, pattern TEXT, customer_id FK, ignore_when_with_customer_id FK NULL, priority INT)`; função `async def customer_from_hostgroups(session, groups: list[dict[str, str]]) -> str | None` com o mesmo contrato de hoje.

- [ ] **Step 1: Failing tests:** `test_hostgroup_bracket_resolves`, `test_zabbix_servers_is_ness` (nomes especiais "Zabbix servers" e "UAT sintético" → Ness, agora como regra cadastrada), `test_alupar_with_pe_prefers_pe` (par {1,5} e {1,6} descarta Alupar, hoje fixo no código), `test_ambiguous_returns_none` (mais de um cliente distinto → `None`).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** regras semeadas com o comportamento atual; `ignore_when_with_customer_id` substitui o `if set(candidates) in ({1,5},{1,6})`.
- [ ] **Step 4: Run** suíte — Expected: PASS.
- [ ] **Step 5: Commit** `feat: regras de grupo de hosts editáveis`.

### Task 3: Modalidade vem do contrato; mapeamento passa a derivar

**Files:**
- Modify: `app/backend/app/integrations/pipeline_health.py`, rota de contratos
- Test: `app/backend/tests/test_pipeline_health.py`

**Interfaces:**
- Consumes: `n_infraops_contracts.modality`, `n_infraops_tenant_mappings.modality`.
- Produces: `async def effective_modality(session, tenant_id: str) -> str | None` (contrato ativo vigente; senão o valor do mapeamento; senão `None`).

- [ ] **Step 1: Failing tests:** `test_modality_from_active_contract`, `test_modality_falls_back_to_mapping`, `test_ended_contract_ignored`, `test_divergence_flagged` (contrato ≠ mapeamento aparece em `/api/pipeline-health` como `modality_divergence=true`, sem escrever).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** `effective_modality` e usá-lo em `pipeline_health.py` (a cobertura declarada continua só para valor não nulo, como hoje).
- [ ] **Step 4: Run** suíte — Expected: PASS.
- [ ] **Step 5: Commit** `feat: modalidade efetiva vem do contrato`.

### Task 4: Parâmetros da política de atendimento por contrato

**Files:**
- Modify: models/migrate/schema, `app/backend/app/api/routers/secops.py` (`_attendance_required`, piso e score), `app/backend/app/core/triage_engine.py`, `app/backend/app/integrations/pipeline_health.py:24-29`
- Create: `app/backend/app/services/policy_params.py`
- Test: `app/backend/tests/test_policy_params.py`

**Interfaces:**
- Consumes: contrato ativo (Task 3).
- Produces: tabela `n_infraops_contract_policy_params(contract_id FK, key TEXT, value_int INT, UNIQUE(contract_id,key))`; chaves: `soc_attend_min_level` (12), `soc_archive_score_floor` (75), `ot_retrospective_hours` (24), `weekly_sample_per_client` (20), `weekly_sample_pct` (10), `source_max_age_seconds` (900), `queue_max_age_seconds` (300); `async def get_param(session, tenant_id: str | None, key: str) -> ParamValue` com `ParamValue(value: int, contractual: bool)`. Sem contrato → padrão interno com `contractual=False`. `ot_retrospective_hours` é limitado a 24 por validação (teto da política SOC).

- [ ] **Step 1: Failing tests:** `test_defaults_equal_legacy_constants`, `test_contract_overrides_default`, `test_param_edit_effective_next_call`, `test_ot_hours_over_24_rejected_422`, `test_non_contractual_flag_present`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** `get_param` e substituir as constantes nos três pontos, sem mudar a regra: o piso de nível 12 não é alterado por contrato abaixo do piso aprovado em 03/11 sem decisão registrada — a API recusa valor menor que 12 em `soc_attend_min_level` (422) e o motivo vai no doc.
- [ ] **Step 4: Run** suíte — Expected: PASS.
- [ ] **Step 5: Mutation:** ignorar o contrato em `get_param` e provar que `test_contract_overrides_default` falha.
- [ ] **Step 6: Commit** `feat: parâmetros de atendimento por contrato`.

### Task 5: Contatos de aviso do cliente

**Files:**
- Modify: models/migrate/schema
- Create: `app/backend/app/api/routers/customer_contacts.py`
- Test: `app/backend/tests/test_customer_contacts.py`

**Interfaces:**
- Produces: tabela `n_infraops_customer_contacts(id, customer_id FK, name, email, phone NULL, role TEXT, notify_severity_min INT, active bool)`; API `GET/POST/PUT/DELETE /api/customers/{id}/contacts` (admin/platform_admin escreve; operator+ lê).

- [ ] **Step 1: Failing tests:** `test_contact_crud`, `test_email_validated_422`, `test_client_role_403`, `test_contact_not_logged_in_audit` (a trilha de mudança guarda só o id e os campos alterados, nunca e-mail ou telefone em log).
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** modelo, migração e API. Nada consome o contato ainda (o P3 avisa operadores); consumo é decisão futura.
- [ ] **Step 4: Run** suíte — Expected: PASS.
- [ ] **Step 5: Commit** `feat: contatos do cliente editáveis`.

### Task 6: Documentação e fechamento

**Files:**
- Modify: `docs/specs/contratos-sla-editaveis.md`, `STATE.md`

- [ ] **Step 1:** documentar o modelo final, as chaves de `policy_params` e seus padrões, o que continua fora (tela, SLM do GLPI, consumo dos contatos, remoção dos cards de exemplo do SecOps).
- [ ] **Step 2:** uma linha no `STATE.md` e checklist de promoção (aplicar migração; conferir seed contra o código antigo; sem tela).
- [ ] **Step 3: Commit** `docs: dados por cliente editáveis`.

## Self-Review

- **Cobertura:** os 8 itens do inventário têm tarefa ou justificativa (item 4 vem do PR de contratos; item 8 fora de escopo, dado de demonstração).
- **Consistência de tipos:** `resolve_glpi_entity_id` muda para assíncrona na Task 1 e é consumida assim nas Tasks 1 e 2; `get_param` e `effective_modality` têm assinatura única, usada nas Tasks 3 e 4.
- **Proporção:** o plano é menor que o código que descreve; corpos de função ficam com o implementador.
- **Risco de ordem:** Task 1 antes da 2; 3 e 4 dependem do PR de contratos na `main`; 5 é independente.
