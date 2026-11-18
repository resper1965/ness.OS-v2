# IA nos chamados — F2: Zabbix como sinal v1 + correlação — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** uma tempestade Zabbix do mesmo cliente vira **um** chamado GLPI. Os demais sinais entram como acompanhamento, e a métrica sinais ÷ chamados passa a ser medida.

**Architecture:**
- O worker monta o envelope de sinal v1 (`zabbix.problem`) a partir do `alert_data`.
- Com a flag ligada, `assign_group` coloca o sinal num grupo do mesmo cliente. Ele roda sob trava por cliente, em transação curta e antes da IA e do GLPI.
- O líder do grupo abre o chamado como hoje. Os seguidores pulam a IA e entram como acompanhamento; se a severidade subir, sobem a urgência e notificam de novo.
- A recuperação de todos os sinais fecha o grupo, e a solução no GLPI também.
- Flag desligada = comportamento de hoje, byte a byte.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL (arrays, advisory lock), Celery, httpx (GLPI), React (AiView).

**Spec:** `docs/superpowers/specs/2026-11-17-ia-tratamento-chamados-design.md` (§4, §6, §7 e F2 em §10). Contrato: `docs/specs/signal-contract-v1.md` + `signal-contract-v1.schema.json`.

## Global Constraints

- **Nunca agrupa entre clientes diferentes.** A chave do cliente é `customer_name.lower().strip()`, a mesma de `tenant_id` no resto do worker.
- **Falha da correlação nunca segura o chamado.** Se `assign_group` levantar exceção, o sinal segue sem grupo, como hoje, com log de warning.
- **O agrupamento é N0:** só regra determinística, sem IA.
- **Sinal de severidade maior nunca é engolido.** Ele sobe a urgência do chamado do grupo (`glpi_urgency`) e notifica de novo pela regra da F1 (`source_urgency` HIGH/CRITICAL).
- **Fechamento do grupo:** só quando todos os sinais se recuperaram na origem, ou quando o chamado é solucionado no GLPI. O Hub **não** soluciona chamado no GLPI (comportamento de hoje mantido).
- **Critérios desta fase:** "mesmo host" e "mesmo trigger em vários hosts". A dependência entre hosts fica de fora: não há dado no GLPI (spec §6).
- **Janelas por cliente**, nas chaves de contrato:
  - `corr_host_window_minutes`: padrão 30;
  - `corr_trigger_window_minutes`: padrão 10;
  - teto 240 nas duas, editáveis pelo PUT de params de contrato que já existe.
- Flag `correlation_enabled: bool = False` (`NINF_CORRELATION_ENABLED`); liga em produção só depois do aviso à operação.
- Migração aditiva e idempotente, com o espelho de `app/migrate.py` idêntico a `sql/001_schema.sql` (teste de paridade).
- O envelope segue o esquema v1 de entrada:
  - `tenant_id` ausente na entrada; o Hub preenche no registro;
  - três instantes distintos, com fuso;
  - `payload` intacto.
- CI precisa passar: `black --check .`, `ruff check app/`, `ruff format --check app/`, `mypy app/ --ignore-missing-imports`, `flake8 --select=E9,F63,F7,F82`, pytest (Postgres 5439), `bash infra/tests/run-hub-local-flow.sh` e frontend lint/typecheck/test/build.
- Código em inglês; commits em português, no formato conventional.

## Review Focus

1. **Dois alertas do mesmo host chegam juntos.** Esperado: um grupo e um chamado (trava por cliente). Teste: T3 `test_concurrent_same_host_one_group`.
2. **O seguidor chega antes de o líder ter o chamado.** Esperado: o incidente é gravado, o retry acontece depois e o acompanhamento entra uma vez só. Teste: T4 `test_follower_waits_for_leader_ticket`.
3. **O mesmo trigger aparece em hosts de dois clientes.** Esperado: dois grupos e dois chamados. Teste: T3 `test_never_groups_across_customers`.
4. **O chamado é solucionado no GLPI e chega sinal novo do mesmo host.** Esperado: grupo novo e chamado novo, nunca acompanhamento em chamado fechado. Teste: T4 `test_resolved_ticket_closes_group`.
5. **Flag desligada.** Esperado: nenhum grupo, e o mesmo número de chamados e notificações de hoje. Teste: T4 `test_flag_off_keeps_one_ticket_per_event`.

---

### Task 1: Envelope de sinal v1 do Zabbix

**Files:**
- Modify: `app/backend/app/integrations/signal_v1.py` (adiciona a função; a do Wazuh fica intacta)
- Modify: `app/backend/app/api/v1/alerts.py:38` e `app/backend/app/api/webhooks.py` (rota Zabbix): carimbar `alert_data["ninf_collected_at"] = datetime.now(UTC).isoformat()` antes do `apply_async`
- Test: `app/backend/tests/test_signal_v1.py`

**Interfaces:**
- Produces:
  - `zabbix_problem_to_signal_v1(alert_data: dict[str, Any], *, source_id: str, received_at: datetime) -> dict[str, Any]`, que devolve o envelope de **entrada**, sem `tenant_id`;
  - `trigger_key(trigger_name: str, host_name: str) -> str`.

Mapeamento (exato):

| Campo | Valor |
|---|---|
| `schema_version` | `"1.0"` |
| `signal_type` | `"zabbix.problem"` |
| `source_id` | o argumento |
| `event_id` | `str(alert_data["event_id"])` |
| `occurred_at` | `alert_data["timestamp"]` |
| `collected_at` | `alert_data["ninf_collected_at"]`; ausente (tarefa antiga na fila) = `received_at − 1 µs`, nunca cópia |
| `received_at` | `received_at.isoformat()` |
| `severity_source` | `{"scheme": "zabbix.severity", "value": alert_data.get("severity")}` |
| `links` | `{"asset": str(host_id)}` |
| `extensions` | `{"zabbix": {"trigger_id": ..., "trigger_key": trigger_key(...)}}` |
| `payload` | `alert_data` sem a chave `ninf_collected_at` |

- O nome do grupo de extensão é o que o esquema aceitar. Confira `extensions` no `.schema.json` e use o padrão dele.
- `trigger_key` troca as ocorrências de `host_name` (se não vazio) por `{HOST}`, depois aplica `strip()` e `lower()`. Assim "Unavailable by ICMP ping" de hosts diferentes casa, e "srv01 is down" vira `{host} is down`.
- `# ponytail:` o trigger casa por nome; o upgrade path é o `templateid` via `trigger.get` quando o nome divergir entre templates.
- Instante inválido ou sem fuso → `SignalRejected` (reaproveitar `_aware`).
- O worker usa `source_id = f"zabbix:{urlparse(settings.zabbix_url).hostname}"`.

- [ ] **Step 1: testes que falham**
  - `test_zabbix_problem_validates_input_schema`: valida com `Draft202012Validator(SCHEMA["$defs"]["input"], format_checker=FormatChecker())`. Verifica que não há `tenant_id`, que `signal_type == "zabbix.problem"` e que os três instantes são distintos.
  - `test_zabbix_payload_intact_without_internal_stamp`: `payload == alert_data` menos `ninf_collected_at`.
  - `test_trigger_key_strips_host`: `trigger_key("srv01 is down", "srv01") == "{host} is down"`, e `trigger_key("Unavailable by ICMP ping", "a") == "unavailable by icmp ping"`.
  - `test_missing_collected_at_never_copies_received`.
  - `test_naive_timestamp_rejected`.
  - `test_alert_route_stamps_collected_at`: o mock do `apply_async` recebe `args[0]["ninf_collected_at"]`.
- [ ] **Step 2:** `pytest tests/test_signal_v1.py -v` → FAIL (função ausente).
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** `pytest tests/test_signal_v1.py tests/test_api.py -v` → PASS.
- [ ] **Step 5:** commit `feat: Zabbix emite envelope de sinal v1`.

### Task 2: Tabela de grupos, parâmetros, flag e urgência no GLPI

**Files:**
- Modify: `app/backend/app/migrate.py`, `app/backend/sql/001_schema.sql` (novo bloco `-- corr:begin/end` ↔ `CORR_SQL`, mais o seed e o CHECK no bloco params)
- Modify: `app/backend/app/models/models.py` (modelo `IncidentGroup`, `Incident.group_id`)
- Modify: `app/backend/app/services/policy_params.py` (`CONTRACT_DEFAULTS`, `CEILINGS`)
- Modify: `app/backend/app/config.py` (`correlation_enabled: bool = False`)
- Modify: `app/backend/app/integrations/glpi.py` (`update_ticket_urgency`)
- Test: `tests/test_bootstrap_sql.py`, `tests/test_policy_params.py`, `tests/test_glpi_urgency_update.py` (novo)

**Interfaces:**
- Produces: `IncidentGroup` (tabela `n_infraops_incident_groups`), `Incident.group_id: int | None`, `GLPIClient.update_ticket_urgency(ticket_id: int, urgency: int) -> None`, `settings.correlation_enabled`, chaves `corr_host_window_minutes` e `corr_trigger_window_minutes`.

DDL (exata, nas duas cópias):

```sql
CREATE TABLE IF NOT EXISTS n_infraops_incident_groups (
    id                 BIGSERIAL PRIMARY KEY,
    customer_name      VARCHAR(255) NOT NULL,
    leader_fingerprint VARCHAR(64) NOT NULL UNIQUE,
    ticket_id          VARCHAR(64),
    max_severity       SMALLINT NOT NULL,
    host_ids           TEXT[] NOT NULL,
    trigger_keys       TEXT[] NOT NULL,
    signal_count       INTEGER NOT NULL DEFAULT 1,
    opened_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_signal_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_incident_groups_open
    ON n_infraops_incident_groups (lower(customer_name), last_signal_at DESC)
    WHERE closed_at IS NULL;
ALTER TABLE n_infraops_incidents
    ADD COLUMN IF NOT EXISTS group_id BIGINT REFERENCES n_infraops_incident_groups(id);
CREATE INDEX IF NOT EXISTS ix_incidents_group_id ON n_infraops_incidents (group_id);
```

- Parâmetros:
  - `CONTRACT_DEFAULTS` recebe `corr_host_window_minutes: 30` e `corr_trigger_window_minutes: 10`, e `CEILINGS` recebe `240` para as duas chaves;
  - o seed do contrato padrão leva as duas linhas;
  - o `ck_policy_params_ceiling` leva `AND (key <> 'corr_host_window_minutes' OR value_int <= 240) AND (key <> 'corr_trigger_window_minutes' OR value_int <= 240)`.
- O CHECK já existe em produção. Use `ALTER TABLE ... DROP CONSTRAINT IF EXISTS ck_policy_params_ceiling` e `ADD CONSTRAINT` com o texto novo, nas duas cópias e em ordem idempotente.
- `update_ticket_urgency` faz `PUT {base_url}/Ticket/{ticket_id}` com `{"input": {"id": ticket_id, "urgency": u, "impact": u}}`, segue o padrão de `add_comment` (`init_session` se faltar token, `_glpi_failure("urgência de ticket", exc)`) e rejeita `u` fora de 1..5 com `ValueError`.

- [ ] **Step 1: testes que falham**
  - paridade de `CORR_SQL` com o bloco `corr` (padrão do teste `ai`);
  - `CONTRACT_DEFAULTS` com as duas chaves; `clamp("corr_host_window_minutes", 999) == 240`;
  - `test_update_ticket_urgency_puts_urgency_and_impact` (`httpx.MockTransport`: método PUT, caminho `/Ticket/77`, corpo exato);
  - `test_update_ticket_urgency_rejects_out_of_range`;
  - teste de migração em Postgres: `run_migrations()` duas vezes sem erro e `PUT` de `corr_host_window_minutes=241` → 422 (padrão dos testes de params em contracts).
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** `pytest tests/test_bootstrap_sql.py tests/test_policy_params.py tests/test_glpi_urgency_update.py -v` mais o teste de contracts → PASS.
- [ ] **Step 5:** commit `feat: grupos de correlação, janelas por cliente e urgência no GLPI`.

### Task 3: Serviço de correlação

**Files:**
- Create: `app/backend/app/services/correlation.py`
- Test: `app/backend/tests/test_correlation.py` (Postgres real)

**Interfaces:**
- Consumes: o envelope da T1 (com `tenant_id` preenchido pelo chamador = nome canônico do cliente), `IncidentGroup`, `get_params`.
- Produces:

```python
@dataclass(frozen=True)
class GroupAssignment:
    group_id: int
    leader: bool          # este sinal abriu o grupo
    ticket_id: str | None # chamado do grupo, quando já existe
    raised: bool          # severidade acima do máximo anterior do grupo
    max_severity: int     # máximo do grupo depois deste sinal

async def assign_group(signal: dict[str, Any], fingerprint: str) -> GroupAssignment
async def set_group_ticket(group_id: int, ticket_id: str) -> None
```

Regras de `assign_group`:
- Abre a própria `SessionLocal`, numa transação. Faz `SET LOCAL lock_timeout = '15s'` e depois `pg_advisory_xact_lock(blake2b("corr:" + tenant))`, no mesmo padrão de `alerts.py:299-310`.
- `OperationalError` → `GLPITransientError`.
- **Retry:** se já existe grupo com `leader_fingerprint == fingerprint`, devolve esse grupo (`leader=True`, `raised=False`).
- **Busca:** grupo aberto (`closed_at IS NULL`) com `lower(customer_name) == tenant`, que satisfaça uma das condições abaixo. Pega o de maior `last_signal_at`.
  - `host = ANY(host_ids)` e `last_signal_at >= now − corr_host_window_minutes`;
  - ou `trigger_key = ANY(trigger_keys)` e `last_signal_at >= now − corr_trigger_window_minutes`.
- **Achou:**
  - acrescenta host e trigger_key aos arrays, sem repetir;
  - faz `signal_count += 1` e `last_signal_at = now`;
  - `raised = sev > max_severity`; se subiu, atualiza `max_severity`;
  - devolve `leader=False`.
- **Não achou:** cria o grupo com `leader_fingerprint=fingerprint` e devolve `leader=True`, `raised=False`.
- **Severidade:** `int(severity_source.value)` quando for int de 0 a 5; senão 3 (regra 7: nunca rebaixa).
- `# ponytail:` uma trava por cliente serializa só a atribuição, nunca a chamada ao GLPI; o upgrade path é a trava por (cliente, host) se a contenção aparecer.

- [ ] **Step 1: testes que falham** (Postgres; inserir o contrato padrão com as janelas pelo próprio `run_migrations` ou pelo fixture dos testes de params)
  - `test_first_signal_opens_group_as_leader`;
  - `test_same_host_within_window_joins`;
  - `test_same_host_after_window_opens_new_group`: muda `last_signal_at` para 31 min atrás;
  - `test_same_trigger_other_host_within_trigger_window_joins`;
  - `test_same_trigger_after_trigger_window_opens_new`: 11 min;
  - `test_never_groups_across_customers`;
  - `test_closed_group_not_joined`;
  - `test_higher_severity_sets_raised`: 3 → 5 dá `raised` True e `max` 5; 5 → 4 dá `raised` False;
  - `test_leader_retry_returns_same_group`;
  - `test_concurrent_same_host_one_group`: `asyncio.gather` de dois `assign_group` com fingerprints diferentes dá um líder, um seguidor e o mesmo `group_id`;
  - `test_customer_window_param_applies`: o contrato do tenant com `corr_host_window_minutes=60` aceita um sinal a 45 min.
- [ ] **Step 2:** `pytest tests/test_correlation.py -v` → FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5:** commit `feat: correlação determinística de sinais por cliente`.

### Task 4: Worker — líder, seguidor, recuperação e solução

**Files:**
- Modify: `app/backend/app/workers/alerts.py` (`_async_process_alert_v1`, `_async_process_recovery`)
- Modify: `app/backend/app/workers/resolution.py` (`resolve_ticket`)
- Test: `app/backend/tests/test_alert_correlation.py` (novo; reusa os fakes de `test_alert_glpi_idempotency.py`)

**Interfaces:**
- Consumes: T1 (`zabbix_problem_to_signal_v1`), T2 (`update_ticket_urgency`, `Incident.group_id`), T3 (`assign_group`, `set_group_ticket`).

Fluxo novo do problema, com `settings.correlation_enabled` ligada; desligada, nada muda:
1. Depois de `canonical_customer`, monta o sinal: `received_at=now`, `source_id` (T1) e `signal["tenant_id"] = customer_name`.
   - O sinal vai junto no `loki_payload["signal"]` **sempre**, com a flag ligada ou desligada.
   - Exceção na montagem = log e segue sem sinal.
2. `assignment = await assign_group(signal, fingerprint)`. Exceção que não seja `GLPITransientError` gera log de warning e `assignment = None`, e o fluxo segue como hoje.
3. **Seguidor** (`assignment.leader is False`):
   - não chama a IA: `analyze_incident(..., skip="grouped")`, gravado com `outcome="skipped_grouped"`;
   - não cria chamado.
   - Se `assignment.ticket_id` for None: grava o incidente (com `group_id`) e levanta `GLPITransientError("group ticket pending")` depois da persistência, pelo caminho que já existe para `glpi_error`. O Celery refaz.
   - Com chamado:
     - `add_comment(int(ticket_id), followup_text, private=False)`; o texto é escapado e traz host, trigger, severidade e event_id;
     - se `assignment.raised`, chama `update_ticket_urgency(ticket_id, glpi_urgency(assignment.max_severity))`.
     - Pula o acompanhamento se o incidente já tiver a tag `ninf_group_followup == "done"`, e grava essa tag depois do sucesso.
     - `# ponytail:` uma queda entre o POST e o commit duplica um acompanhamento; o upgrade path é um marcador no conteúdo e uma busca antes do POST.
   - O incidente do seguidor fica com `deskmanager_ticket_id = None` (o chamado é o do grupo; `resolution.py` busca o líder pelo ticket) e com a tag `ninf_group_ticket_id`.
   - **Notifica** só se `assignment.raised` e a regra da F1 der verdadeiro.
4. **Líder:** fluxo de hoje, com `ensure_glpi_ticket_serialized(fingerprint=fingerprint)`. Depois de obter `ticket_id`, chama `set_group_ticket(group_id, str(ticket_id))` e grava `group_id` no incidente.
5. **Recuperação** (`_async_process_recovery`), dentro da mesma transação com `FOR UPDATE` do grupo:
   - se o incidente tem `group_id`, conta os membros com `ninf_zabbix_status != "resolved"`, já contando este como resolvido;
   - zero membros pendentes → `closed_at = now`.
   - Depois do commit, e só se `signal_count > 1` e houver chamado no grupo:
     - um acompanhamento "Sinal recuperado na origem: host, trigger";
     - quando o grupo fecha, mais um: "Todos os N sinais do grupo se recuperaram na origem".
   - Falha no GLPI aqui = log de erro, sem exceção.
   - `# ponytail:` acompanhamento de recuperação perdido numa queda do GLPI; o estado continua no Hub. O upgrade path é uma fila de acompanhamentos.
   - O GLPI **não** é solucionado.
6. **Solução** (`resolve_ticket`), no mesmo commit que já marca `resolved`:
   - se `incident.group_id`, faz `closed_at = coalesce(closed_at, now)` no grupo;
   - os membros com `status != "resolved"` passam a `resolved`, cada um com um `IncidentAction(action="group_resolved", note=f"ticket={ticket_id}")`.
   - O ack no Zabbix fica só para o líder, como hoje. `# ponytail:` membros sem ack no Zabbix; o upgrade path é um laço com `acknowledge_resolution_once` por membro.

- [ ] **Step 1: testes que falham** (Postgres mais GLPI falso; `settings.correlation_enabled=True` por monkeypatch, salvo no caso da flag)
  - `test_storm_of_50_same_trigger_is_one_ticket`: 50 alertas, mesmo trigger, hosts distintos, mesmo cliente → `create_ticket` 1×, `add_comment` de acompanhamento 49× e IA chamada 1×.
  - `test_follower_waits_for_leader_ticket`: o seguidor processado antes de `set_group_ticket` levanta `GLPITransientError`, e o incidente fica gravado com `group_id`. Depois de `set_group_ticket`, o reprocessamento faz 1 acompanhamento, e um segundo reprocessamento faz 0.
  - `test_higher_severity_raises_urgency_and_notifies`: o líder com severidade 3 e o seguidor com 5 dão `update_ticket_urgency(ticket, 5)` e uma notificação; um seguidor com 4 depois não dá nenhuma das duas.
  - `test_recovery_of_all_closes_group_with_followups`: com 3 membros, as recuperações 1 e 2 dão 1 acompanhamento cada e o grupo continua aberto; a terceira dá 2 acompanhamentos e `closed_at` preenchido. Nenhuma chamada de solução no GLPI.
  - `test_resolved_ticket_closes_group`: `resolve_ticket` no chamado do líder fecha o grupo e resolve os membros. Um alerta novo do mesmo host vira líder de um grupo novo e chama `create_ticket`.
  - `test_flag_off_keeps_one_ticket_per_event`: 3 alertas do mesmo host dão 3 `create_ticket` e nenhuma linha em `n_infraops_incident_groups`.
  - `test_correlation_failure_never_blocks_ticket`: `assign_group` levantando `RuntimeError` mantém `create_ticket` chamado.
  - Os testes de `test_alert_glpi_idempotency.py` seguem verdes sem mudança (a flag fica desligada por padrão).
- [ ] **Step 2:** `pytest tests/test_alert_correlation.py -v` → FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** a suíte completa do backend e `bash infra/tests/run-hub-local-flow.sh` → PASS.
- [ ] **Step 5:** commit `feat: tempestade do Zabbix vira um chamado com acompanhamentos`.

### Task 5: Métrica sinais ÷ chamados, tela e fechamento

**Files:**
- Modify: `app/backend/app/api/routers/ai.py` (`/api/ai/metrics`)
- Modify: `app/frontend/src/components/AiView.tsx` e o tipo da resposta
- Modify: `docs/superpowers/specs/2026-11-17-ia-tratamento-chamados-design.md` (linha de estado), `STATE.md`
- Create: `docs/execution/ai-f2-aviso-operacao.md`
- Test: `tests/test_ai_api.py`, o teste do `AiView`

**Interfaces:**
- Produces: `metrics["correlation"] = {"signals": int, "tickets": int, "ratio": float | None}`.
  - **signals:** incidentes com `created_at` na janela `days`;
  - **tickets:** desses, os com `deskmanager_ticket_id IS NOT NULL`;
  - **ratio:** `signals / tickets`, ou `null` quando `tickets == 0`.
  - Com `customer_id` (ou o escopo do tenant), filtra por `lower(tags->>'ninf_customer_name')`.

- [ ] **Step 1: testes que falham**
  - `test_metrics_correlation_ratio`: 5 incidentes, 2 com chamado → `ratio == 2.5`; os de outro cliente ficam fora com o filtro.
  - `test_metrics_correlation_no_tickets_is_null`.
  - Teste do frontend: o card "Sinais ÷ chamados" mostra `2,5`, e `null` vira `—`.
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** o CI completo da Global Constraints → PASS.
- [ ] **Step 5:** docs.
  - O aviso à operação, curto e em português, diz:
    - com `NINF_CORRELATION_ENABLED=true`, sinais do mesmo cliente e do mesmo host (30 min) ou do mesmo trigger (10 min) entram como acompanhamento do chamado aberto;
    - severidade maior sobe a urgência e notifica;
    - o grupo fecha quando todos se recuperam ou quando o chamado é solucionado;
    - as janelas são editáveis por contrato, até 240 min;
    - verificação pré-promoção: rodar com a flag desligada, ligar num horário calmo e conferir a razão na tela "IA".
  - No `STATE.md`, Próximo passo: "promover F2 com a flag desligada, ligar após aviso e OK do Ricardo; depois F3 (Wazuh→GLPI)".
- [ ] **Step 6:** commit `docs: fecha F2 da IA nos chamados`.
