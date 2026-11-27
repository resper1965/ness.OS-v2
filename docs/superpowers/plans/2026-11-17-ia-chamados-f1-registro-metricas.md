# IA nos chamados — F1: registro, retorno e métricas — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Toda saída de IA (NOC e SOC) gravada no banco com custo e divergência, com retorno do analista, teto global de custo, opção por cliente e tela de métricas. A IA perde o poder de subir a urgência.

**Architecture:** Uma tabela nova, `n_ai_decisions`, uma linha por chamada de IA, ligada ao incidente/chamado (NOC) ou à `SocDecision` (SOC). Duas portas, verificadas no Hub **antes** de chamar o modelo: cliente com IA externa desligada e teto mensal atingido. Se uma delas fecha, a etapa vira `manual_triage` e o chamado segue normal. Um router `/api/ai` serve o retorno e as métricas; a tela fica em `?view=ai`.

**Tech Stack:** FastAPI + SQLAlchemy async, migração idempotente em `app/migrate.py` espelhada em `sql/001_schema.sql`, pytest (Postgres real via `NINF_TEST_PG_URL`), React 19 + Vite + Vitest.

**Spec:** `docs/superpowers/specs/2026-11-17-ia-tratamento-chamados-design.md` (seções 3, 5, 7, 8 e F1 da seção 10).

Raiz do backend: `app/backend/`. Os caminhos abaixo partem dela, exceto onde começam com `app/frontend/` ou `docs/`.

## Global Constraints

- O atendimento e a urgência independem do modelo: a urgência do GLPI e a decisão de notificar vêm só da severidade da origem.
- Falha da IA, cliente desligado ou teto atingido **nunca** seguram o chamado (`manual_triage` e o fluxo segue).
- Sinal sem cliente não vai à IA (já vale; não regredir).
- Teto global, valor inicial **US$ 50/mês** (`5000` centavos), editável pelo platform_admin. Ao atingir o teto: a IA é pulada e é enviado **um** e-mail por mês ao Ricardo.
- "IA externa permitida" por cliente, **ligada por padrão**.
- Nenhum prompt bruto é persistido. Grava-se a entrada **já sanitizada** (`AIRequestV1.model_dump`) e a resposta validada.
- Migração aditiva e idempotente (`IF NOT EXISTS`). Rollback = imagem anterior; a tabela e a coluna podem ficar.
- Commits em português, conventional. Código em inglês.

## Review Focus

1. **Corrida no teto:** dois workers podem passar da porta no mesmo instante e estourar o teto em uma chamada. É aceitável: o limite é suave, e o limite rígido de US$ 50 continua na chave da OpenRouter. Teste: com o teto já atingido, nenhuma chamada HTTP é feita (Task 2).
2. **OpenRouter sem `usage.cost`:** o custo fica `NULL`, não `0`. As métricas somam ignorando `NULL` e expõem `cost_missing` (Tasks 1 e 5).
3. **Retorno vindo de outro cliente:** um usuário de tenant só dá retorno nas decisões do próprio cliente; caso contrário, 404 (Task 5).
4. **Reprocessamento do mesmo evento Zabbix:** o replay não cria segunda decisão para o mesmo `(kind, fingerprint, event_id)` (Task 3).
5. **Notificação depois da mudança:** com a IA dizendo CRITICAL e a severidade da origem 3, **não** há push. Com a origem 4, há push mesmo se a IA disser LOW (Task 3).

---

### Task 1: Tabela `n_ai_decisions`, coluna do cliente, parâmetro de teto e registro da chamada

**Files:**
- Modify: `app/models/models.py` (novo `AIDecision` depois de `SocDecision`; `Customer.ai_external_allowed`)
- Modify: `app/migrate.py`, `sql/001_schema.sql` (mesmo DDL)
- Modify: `app/services/policy_params.py` (`PLATFORM_DEFAULTS["ai_monthly_budget_cents"] = 5000`; `PLATFORM_MAX` para essa chave `= 1_000_000`)
- Modify: `app/core/ai_context.py` (`log_ai_call` passa a devolver `AICall`)
- Modify: `app/integrations/llm.py` (pede `"usage": {"include": True}` no corpo e devolve o `model` da resposta em `usage["model"]`)
- Test: `tests/test_bootstrap_sql.py`, `tests/test_ai_context.py`, `tests/test_llm.py`

**Interfaces:**
- Produces:
  - `AIDecision` (tabela `n_ai_decisions`), com as colunas:
    - `id BIGSERIAL`
    - `kind VARCHAR(32) NOT NULL` (`incident_analysis` | `soc_triage`)
    - `customer_id VARCHAR(128) NOT NULL`
    - `incident_id BIGINT NULL`
    - `soc_decision_id BIGINT NULL`
    - `ticket_id VARCHAR(64) NULL`
    - `source_ref VARCHAR(255) NOT NULL` (NOC: `fingerprint:event_id`; SOC: `dedup_key` ou `soc:<id>`)
    - `outcome VARCHAR(24) NOT NULL` (`ok` | `error` | `skipped_customer` | `skipped_budget` | `no_key`)
    - `model VARCHAR(128) NULL`
    - `prompt_version VARCHAR(32) NOT NULL`
    - `request JSONB NOT NULL DEFAULT '{}'`
    - `response JSONB NOT NULL DEFAULT '{}'`
    - `rule_value VARCHAR(32) NULL`
    - `model_value VARCHAR(32) NULL`
    - `divergent BOOLEAN NOT NULL DEFAULT false`
    - `latency_ms INT NULL`
    - `prompt_tokens INT NULL`
    - `completion_tokens INT NULL`
    - `cost_usd NUMERIC(10,6) NULL`
    - `feedback VARCHAR(16) NULL` (`useful` | `wrong` | `unread`)
    - `feedback_user_id BIGINT NULL`
    - `feedback_at TIMESTAMPTZ NULL`
    - `final_label VARCHAR(64) NULL`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - Índices da tabela:
    - `uq_ai_decisions_ref UNIQUE (kind, source_ref)`
    - `ix_ai_decisions_customer_created (customer_id, created_at DESC)`
    - `ix_ai_decisions_incident (incident_id) WHERE incident_id IS NOT NULL`
  - `Customer.ai_external_allowed: bool`, coluna `BOOLEAN NOT NULL DEFAULT true`.
  - `@dataclass(frozen=True) class AICall: kind: str; outcome: str; model: str | None; latency_ms: int; prompt_tokens: int | None; completion_tokens: int | None; cost_usd: float | None`
  - `log_ai_call(kind, outcome, started, usage=None) -> AICall`. O log JSON atual continua igual, acrescido de `model` e `cost_usd`.

- [ ] **Step 1: Write the failing tests**
  - `test_bootstrap_sql.py::test_ai_decisions_table_and_customer_flag_in_bootstrap`: `CREATE TABLE n_ai_decisions` existe em `001_schema.sql`; os três índices acima aparecem com o mesmo DDL em `migrate.py` e no bootstrap (mesmo `_norm` dos testes vizinhos); `ai_external_allowed BOOLEAN NOT NULL DEFAULT true` aparece nos dois.
  - `test_ai_context.py::test_log_ai_call_returns_call_with_cost_and_model`: `usage={"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0012, "model": "google/gemini-2.5-flash"}` gera um `AICall` com `cost_usd == 0.0012`, `model == "google/gemini-2.5-flash"` e `latency_ms >= 0`. Com `usage=None`, devolve `cost_usd is None` e `model is None`.
  - `test_llm.py::test_request_asks_usage_accounting_and_returns_model`: o corpo enviado (via `MockTransport`) tem `body["usage"] == {"include": True}`. Uma resposta `{"model": "m", "choices": [...], "usage": {"cost": 0.1}}` devolve `usage == {"cost": 0.1, "model": "m"}`.

- [ ] **Step 2: Run, expect FAIL**: `cd app/backend && pytest tests/test_bootstrap_sql.py tests/test_ai_context.py tests/test_llm.py -q`

- [ ] **Step 3: Implement.** O DDL vai num bloco `-- ai:begin` / `-- ai:end` em `001_schema.sql` e numa constante `AI_SQL` em `migrate.py`, aplicada em `run_migrations()` igual a `apply_params_sql`. No `_parse` do `llm.py`, `usage = {**(result.get("usage") or {}), "model": result.get("model")}` quando `model` existe.

- [ ] **Step 4: Run, expect PASS** (mesmo comando), mais `black --check . && flake8`.

- [ ] **Step 5: Commit** `feat: tabela de decisões de IA, teto global e custo por chamada`

---

### Task 2: Portas antes do modelo — cliente desligado e teto mensal

**Files:**
- Create: `app/services/ai_gate.py`
- Modify: `app/config.py` (`ai_budget_alert_email: str = ""`)
- Test: `tests/test_ai_gate.py` (Postgres real; padrão de fixture de `test_secops_postgres.py`)

**Interfaces:**
- Consumes: `AIDecision`, `Customer.ai_external_allowed`, `platform_params(session)` e `ResendEmailClient.from_settings().send(to=, subject=, idempotency_key=, text=)`.
- Produces: `async def ai_gate(session, customer_key: str) -> str | None`.
  - Devolve `None` quando a IA pode rodar.
  - Devolve `"skipped_customer"` quando o cliente (`Customer.key == customer_key`) tem `ai_external_allowed = false`.
  - Devolve `"skipped_budget"` quando `SUM(cost_usd)` do mês corrente (UTC) em `n_ai_decisions` × 100 ≥ `ai_monthly_budget_cents`.
  - O cliente vem antes do teto.
  - Na **primeira** vez no mês que devolve `skipped_budget` (nenhuma linha `skipped_budget` no mês), envia o e-mail para `settings.ai_budget_alert_email` com `idempotency_key=f"ai-budget-{YYYY-MM}"`. Se o e-mail estiver vazio ou desligado, registra só warning. Falha de envio nunca propaga.

- [ ] **Step 1: Write the failing tests**
  - `test_gate_open_by_default`: cliente sem flag explícita e sem gasto devolve `None`.
  - `test_gate_customer_disabled`: com `ai_external_allowed=False`, devolve `"skipped_customer"`.
  - `test_gate_budget_reached_sends_one_email`: linhas do mês somando `cost_usd = 50.00` com o parâmetro padrão devolvem `"skipped_budget"`. O cliente de e-mail falso é chamado uma vez. Depois de gravar uma linha `skipped_budget`, a segunda chamada devolve `"skipped_budget"` com o e-mail ainda chamado 1 vez.
  - `test_gate_ignores_previous_month_and_null_cost`: gasto de US$ 60 no mês anterior mais uma linha do mês com `cost_usd NULL` devolvem `None`.

- [ ] **Step 2: Run, expect FAIL**: `NINF_TEST_PG_URL=postgresql+asyncpg://dev:dev@127.0.0.1:5439/app pytest tests/test_ai_gate.py -q`. O banco de teste sobe com `PG_PORTA=5439 docker compose -p ness-os -f /srv/dev/bin/postgres.yml up -d --wait`.

- [ ] **Step 3: Implement `ai_gate`.**

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Commit** `feat: porta de IA por cliente e teto mensal com alerta`

---

### Task 3: NOC — tirar o poder de urgência da IA, aplicar a porta e registrar a decisão

**Files:**
- Modify: `app/ml/analyzer.py`
- Modify: `app/workers/alerts.py` (`_async_process_alert_v1`, l.405–537)
- Create: `app/services/ai_decisions.py`
- Test: `tests/test_analyzer_fallback.py`, `tests/test_alert_glpi_idempotency.py` (ou o teste de worker que já faz monkeypatch de `SessionLocal`) e `tests/test_ai_decisions.py`

**Interfaces:**
- Consumes: `ai_gate`, `AICall` e `AIDecision`.
- Produces:
  - `PROMPT_VERSION_NOC = "noc-2026-11-17"` em `analyzer.py`.
  - `AIAnalysisResult` ganha `PrivateAttr`s `_call: AICall | None` e `_request: dict`.
  - O `analyze_incident(...)` fica com a mesma assinatura e passa a aceitar o kwarg `skip: str | None = None`. Com `skip`, devolve `manual_triage` **sem HTTP** e com `_call.outcome == skip`.
  - **Removida** a elevação `if URGENCY_ORDER.index(...) < ...: analysis.urgency = minimum`. `analysis.urgency` passa a ser a opinião crua do modelo.
  - `async def record_ai_decision(session, *, kind: str, customer_id: str, source_ref: str, call: AICall, prompt_version: str, request: dict, response: dict, rule_value: str | None, model_value: str | None, incident_id: int | None = None, soc_decision_id: int | None = None, ticket_id: str | None = None) -> int | None`.
    - Usa `INSERT ... ON CONFLICT (kind, source_ref) DO NOTHING` e devolve o id, ou `None` no replay.
    - `divergent = rule_value is not None and model_value is not None and rule_value != model_value`.
    - No NOC, `model_value` vem de `"ISOLATE"` se `isolation_required`, senão de `analysis.urgency`. Assim o pedido de isolamento também conta como divergência.

- [ ] **Step 1: Write the failing tests**
  - `test_analyzer_fallback.py::test_model_urgency_is_not_raised_to_source`: com o modelo devolvendo `urgency="LOW"` e a severidade 5, `result.urgency == "LOW"`.
  - `test_analyzer_fallback.py::test_skip_makes_no_http_call`: `skip="skipped_budget"` com um `AsyncClient` que levanta erro devolve `manual_triage` e `result._call.outcome == "skipped_budget"`.
  - `test_alert_glpi_idempotency.py` (ou o teste de worker que já existe) `test_notification_follows_source_severity_only`, parametrizado assim:
    - severidade 3 + IA CRITICAL: sem push;
    - severidade 4 + IA LOW: com push;
    - severidade 3 + IA `isolation_required`: sem push.
  - `test_alert_glpi_idempotency.py::test_glpi_urgency_unchanged`: a urgência do GLPI continua `glpi_urgency(severity)`.
  - `test_ai_decisions.py` (Postgres real):
    - `test_record_marks_divergence_and_is_idempotent`: `rule_value="MEDIUM"` com `model_value="CRITICAL"` resulta em `divergent is True`. A segunda chamada com o mesmo `(kind, source_ref)` devolve `None` e deixa 1 linha.
    - `test_worker_records_decision_with_incident_and_ticket`: depois de `_async_process_alert_v1` com GLPI falso devolvendo o ticket 77, existe 1 linha com `kind="incident_analysis"`, `incident_id` igual ao do incidente, `ticket_id="77"`, `request` sem `customer_metadata` bruto e `prompt_version == PROMPT_VERSION_NOC`.

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**
  - No worker: abrir a sessão antes da análise para chamar `skip = await ai_gate(session, customer_name.lower().strip())` (sessão curta e própria) e passar `skip` a `analyze_incident`.
  - Trocar `notify` para `source_urgency(alert_data) in ("HIGH", "CRITICAL")`.
  - O Loki passa a mandar `severity=source_urgency(alert_data).lower()` e mantém `analysis.model_dump()` no payload.
  - No bloco de persistência (l.493), depois do `flush` do incidente, chamar `record_ai_decision` na mesma transação, com `source_ref=f"{fingerprint}:{event_id}"` e `rule_value=source_urgency(alert_data)`.
  - Falha no `record_ai_decision` gera log e **não** aborta: usar `session.begin_nested()`.

- [ ] **Step 4: Run, expect PASS**, mais toda a suíte: `pytest -q`.

- [ ] **Step 5: Commit** `fix: IA do NOC deixa de subir urgência; decisão registrada no banco`

---

### Task 4: SOC — porta, registro e divergência motor × modelo (E1, Vigil descontinuado)

**Files:**
- Modify: `app/api/routers/secops.py` (`triage_alert`, l.712–888)
- Modify: `app/integrations/soc_agent.py` (`triage_wazuh_alert` aceita `skip: str | None = None` e devolve também `_call`/`_request` por chaves privadas `"_ai_call"`/`"_ai_request"`, removidas antes da resposta da API)
- Test: `tests/test_secops_postgres.py`, `tests/test_secops_triage_api.py`

**Interfaces:**
- Consumes: `ai_gate` e `record_ai_decision`.
- Produces:
  - `PROMPT_VERSION_SOC = "soc-2026-11-17"`.
  - Regra de divergência, função pura em `secops.py`: `def soc_divergent(engine_action: str, classification: str) -> bool`. Devolve `(engine_action == "TRIAGE_L2" and classification in {"FP","LOW"}) or (engine_action == "TRIAGE_L1" and classification in {"HIGH","CRIT"})`.
  - No registro, `rule_value = eval_result.action.value` e `model_value = classification`. Como os vocabulários diferem, `divergent` vem de `soc_divergent`, não da comparação direta. `record_ai_decision` ganha o kwarg `divergent: bool | None = None`, que prevalece quando é informado.

- [ ] **Step 1: Write the failing tests**
  - `test_soc_divergent` (parametrizado): L2+FP → True; L2+HIGH → False; L1+CRIT → True; L1+MED → False.
  - `test_secops_postgres.py::test_triage_records_ai_decision_linked_to_soc_decision`: alerta atendido gera 1 linha `kind="soc_triage"` com `soc_decision_id == decision.id`. O `attendance_required` da resposta é igual ao de antes da mudança.
  - `test_secops_postgres.py::test_archived_and_pending_do_not_record`: arquivado (`ARCHIVE_NO_LLM`) e sem cliente não geram linha (não houve IA).
  - `test_secops_triage_api.py::test_customer_disabled_skips_model`: com `ai_gate` devolvendo `"skipped_customer"`, `triage_wazuh_alert` não chama HTTP, a resposta tem o fallback manual e o atendimento não muda.

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.** A porta é chamada só no ramo `else` (atendido e com cliente). O `record_ai_decision` roda depois do `commit` da `SocDecision`, em `begin_nested` próprio. Falha no registro gera log e não muda a resposta.

- [ ] **Step 4: Run, expect PASS** (suíte inteira).

- [ ] **Step 5: Commit** `feat: decisão SOC registrada com divergência motor x modelo`

---

### Task 5: API `/api/ai` — retorno do analista, opção do cliente e métricas

**Files:**
- Create: `app/api/routers/ai.py`; registrar em `app/main.py`
- Modify: `app/api/routers/customers.py` (`CustomerPatch.ai_external_allowed: bool | None = None`; `_fields`/`_out` incluem o campo)
- Modify: `app/workers/resolution.py` e `app/integrations/glpi.py` (`ticket_resolution` passa a devolver também `category_id: int | None` = `ticket.get("itilcategories_id")`). `resolve_ticket` grava `final_label = str(category_id)` nas `n_ai_decisions` do incidente.
- Test: `tests/test_ai_api.py`, `tests/test_resolution_sync.py`, `tests/test_customers.py`

**Interfaces:**
- Produces:
  - `POST /api/ai/decisions/{id}/feedback`, corpo `{"verdict": "useful"|"wrong"|"unread"}`, `require_noc`. O escopo vem de `resolve_tenant_scope(user, None)`: decisão de outro cliente devolve 404. Grava `feedback`, `feedback_user_id` e `feedback_at`. Pode ser sobrescrito pelo mesmo usuário ou por outro: vale o último.
  - `GET /api/ai/decisions?kind=&customer_id=&divergent=&limit=50`, `require_noc`: lista recente, **sem** `request`/`response` completos (só `id`, `kind`, `customer_id`, `ticket_id`, `outcome`, `model`, `rule_value`, `model_value`, `divergent`, `feedback`, `cost_usd` e `created_at`).
  - `GET /api/ai/metrics?days=30&customer_id=`, `require_noc`. Agrega por `kind` e devolve:
```json
{"window_days":30,"budget":{"month_cost_usd":0.0,"limit_usd":50.0},
 "by_kind":{"incident_analysis":{"total":0,"by_outcome":{},"divergence_rate":0.0,
  "feedback":{"useful":0,"wrong":0,"unread":0,"none":0},"useful_rate":null,
  "cost_usd":0.0,"cost_missing":0,"avg_latency_ms":null,"failure_rate":0.0,
  "mttr_minutes":{"useful":null,"other":null}}}}
```
    - As taxas usam como denominador `total` (divergência e falha) ou o total com retorno (`useful_rate`).
    - `mttr_minutes` mede o tempo entre `created_at` e a resolução do incidente ligado (`tags["resolution_synced_at"]` ou o campo que `resolution.py` já grava), separado por `feedback == "useful"` ou não.
    - `sinais ÷ chamados` fica fora: é da F2.

- [ ] **Step 1: Write the failing tests** (`test_ai_api.py`, Postgres real):
  - `test_feedback_cross_tenant_is_404`;
  - `test_feedback_overwrites`;
  - `test_metrics_rates_and_null_cost`: 4 linhas, 1 divergente, 1 `error`, 1 com custo `NULL`. O resultado tem `divergence_rate == 0.25`, `failure_rate == 0.25` e `cost_missing == 1`;
  - `test_metrics_budget_reflects_platform_param`.
  - Em `test_resolution_sync.py::test_final_label_from_glpi_category`: o ticket falso com `itilcategories_id=12` grava `final_label == "12"` nas decisões do incidente.
  - Em `test_customers.py::test_patch_ai_external_allowed`: o `PUT` com `{"ai_external_allowed": false}` persiste e aparece no `GET`.

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run, expect PASS** (suíte inteira).

- [ ] **Step 5: Commit** `feat: API de retorno e métricas da IA`

---

### Task 6: Tela "IA" no Hub e opção no cadastro do cliente

**Files:**
- Create: `app/frontend/src/components/AiView.tsx`, `app/frontend/src/components/AiView.test.tsx`
- Modify: `app/frontend/src/App.tsx` (`View` ganha `'ai'`, título "IA", liberado em `allowedView` quando `isOperator`)
- Modify: `app/frontend/src/components/CustomersScreen.tsx` (ou o formulário em `components/customers/`): checkbox "IA externa permitida"

**Interfaces:**
- Consumes: `GET /api/ai/metrics`, `GET /api/ai/decisions` e `POST /api/ai/decisions/{id}/feedback` via `request<T>()` de `src/http.ts`.
- Produces:
  - Tela com cartões por `kind`: total, divergência, "útil", falha, custo do mês sobre o teto e MTTR útil × outro.
  - Tabela das decisões recentes com filtro "só divergentes" e três botões de retorno por linha, cada um com `aria-label`.
  - Custo `NULL` aparece como "—", nunca "0".

- [ ] **Step 1: Write the failing tests** (`AiView.test.tsx`, com `fetch` mockado como nos testes vizinhos):
  - os cartões mostram `25%` para `divergence_rate: 0.25`;
  - clicar em "Útil" faz `POST` com `{"verdict":"useful"}` e a linha passa a mostrar "útil";
  - `cost_usd: null` aparece como "—".

- [ ] **Step 2: Run, expect FAIL**: `cd app/frontend && npm test -- AiView`

- [ ] **Step 3: Implement** no padrão visual de `SocView.tsx` (kit `.nx`, sem dependência nova).

- [ ] **Step 4: Run, expect PASS**: `npm run lint && npm run typecheck && npm test && npm run build`

- [ ] **Step 5: Commit** `feat: tela de métricas e retorno da IA`

---

### Task 7: Fechamento — documentação, aviso à operação e STATE

**Files:**
- Modify: `docs/superpowers/specs/2026-11-17-ia-tratamento-chamados-design.md` (F1 marcada como entregue, com o PR)
- Modify: `STATE.md` (Próximo passo: promover a F1 depois do aviso à operação; em seguida, F2)
- Create: `docs/execution/ai-f1-aviso-operacao.md`: aviso curto à equipe. A partir da promoção, o push de alerta só sai pela severidade do Zabbix (≥ 4); a IA não escala mais. Divergências aparecem na tela "IA".

- [ ] **Step 1:** Rodar a verificação completa:
  - backend: `black --check . && flake8 && NINF_TEST_PG_URL=... pytest -q`;
  - frontend: `npm run lint && npm run typecheck && npm test && npm run build`;
  - `bash infra/tests/run-hub-local-flow.sh`.

  Esperado: tudo verde.
- [ ] **Step 2:** Atualizar os documentos acima.
- [ ] **Step 3: Commit** `docs: fecha F1 da IA nos chamados`. Abrir PR com `Closes` da issue criada para a F1.

**Promoção:** gate normal do Hub, com OK do Ricardo **depois** de o aviso ser enviado à operação. O rollback é a imagem anterior. A tabela e a coluna podem ficar, pois a mudança é aditiva.

---

## Fora deste plano

- **F2 a F6** (correlação, Wazuh até o GLPI, Action1, ferramenta de cliente): um plano por fase, depois da F1 em produção.
- **Acerto da IA do NOC pela categoria:** hoje a IA do NOC não sugere categoria (ela vem de palavra-chave). A F1 grava `final_label` para a comparação começar quando a IA sugerir categoria. Até lá, o acerto do NOC é medido pelo retorno "útil" e pela divergência.
- **Botão de retorno dentro do GLPI:** a F1 tem o retorno só no Hub; o GLPI fica para depois.
