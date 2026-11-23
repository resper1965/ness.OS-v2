# IA nos chamados — F2: repetição e medição — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** quando o mesmo trigger dispara de novo no mesmo host com o chamado ainda aberto, o alerta vira acompanhamento desse chamado, não um chamado novo. Além disso, a F2 mede se há tempestade de alertas que justifique mais.

**Architecture:**
- Antes de abrir o chamado, o worker procura o incidente raiz aberto do mesmo cliente, host e trigger. Achando, grava o novo incidente como repetição (`repeat_of_id`), comenta no chamado da raiz e não chama a IA.
- A solução no GLPI resolve a raiz e as repetições dela.
- A medição tem duas partes: a razão sinais ÷ chamados na tela "IA" e uma consulta histórica de tempestade que roda em produção só para leitura.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL, Celery, React.

**Spec:** `docs/superpowers/specs/2026-11-17-ia-tratamento-chamados-design.md` (§4.1, §6, F2 em §10).

## Global Constraints

- Repetição = **o mesmo cliente** (`lower(tags->>'ninf_customer_name')`), o mesmo `host_id` e o mesmo `trigger_id`. Nunca entre clientes; nunca por trigger em outro host.
- Só vale para sinal de estado (Zabbix). Nada de Wazuh nesta fase.
- Flag `zabbix_repeat_followup_enabled: bool = False` (`NINF_ZABBIX_REPEAT_FOLLOWUP_ENABLED`). Com a flag desligada, o comportamento é o de hoje.
- Falha na busca da raiz nunca segura o chamado: em exceção, log de warning e o fluxo de hoje (chamado novo).
- A notificação segue a regra da F1, sem mudança.
- `resolution.py` busca o incidente por `deskmanager_ticket_id` com `scalar_one_or_none`, então a repetição **nunca** grava `deskmanager_ticket_id`. O chamado dela fica na tag `ninf_repeat_ticket_id`.
- Migração aditiva e idempotente, com o espelho de `migrate.py` idêntico a `sql/001_schema.sql`.
- CI: `black --check .`, `ruff check app/`, `ruff format --check app/`, `mypy app/ --ignore-missing-imports`, `flake8 --select=E9,F63,F7,F82`, pytest com Postgres 5439, `bash infra/tests/run-hub-local-flow.sh` e frontend lint/typecheck/test/build.
- Código em inglês; commits em português, no formato conventional.

## Review Focus

1. **Flapping: problema, recuperação, problema, com o chamado aberto.** Esperado: o segundo problema vira acompanhamento. A raiz já recuperada na origem não impede a repetição, porque o que conta é o chamado aberto. Teste: T1 `test_flapping_after_recovery_is_followup`.
2. **O chamado da raiz foi solucionado.** Esperado: chamado novo e raiz nova. Teste: T1 `test_resolved_root_opens_new_ticket`.
3. **Retry do Celery da repetição.** Esperado: um acompanhamento só. Teste: T1 `test_repeat_retry_single_followup`.
4. **A raiz ainda não tem chamado (GLPI falhou).** Esperado: a repetição não pega uma raiz sem chamado e segue o fluxo de hoje. Teste: T1 `test_root_without_ticket_is_not_reused`.
5. **O mesmo trigger e host em clientes diferentes.** Esperado: dois chamados. Teste: T1 `test_repeat_never_crosses_customers`.

---

### Task 1: Repetição vira acompanhamento

**Files:**
- Modify: `app/backend/app/migrate.py`, `app/backend/sql/001_schema.sql` (bloco `-- repeat:begin/end` ↔ `REPEAT_SQL`)
- Modify: `app/backend/app/models/models.py` (`Incident.repeat_of_id`)
- Modify: `app/backend/app/config.py` (flag)
- Modify: `app/backend/app/workers/alerts.py` (`_async_process_alert_v1`)
- Modify: `app/backend/app/workers/resolution.py` (`resolve_ticket`)
- Test: `app/backend/tests/test_alert_repeat.py` (novo; Postgres e o GLPI falso de `test_alert_glpi_idempotency.py`), `tests/test_bootstrap_sql.py`

**Interfaces:**
- Produces:
  - `Incident.repeat_of_id: int | None`;
  - `find_open_root(session, *, customer_name: str, host_id: str, trigger_id: str, fingerprint: str) -> Incident | None` em `alerts.py`;
  - o outcome de IA `"skipped_repeat"`.

DDL (nas duas cópias):

```sql
ALTER TABLE n_infraops_incidents
    ADD COLUMN IF NOT EXISTS repeat_of_id BIGINT REFERENCES n_infraops_incidents(id);
CREATE INDEX IF NOT EXISTS ix_incidents_open_root
    ON n_infraops_incidents (host_id, trigger_id)
    WHERE repeat_of_id IS NULL AND status NOT IN ('resolved','closed');
```

`find_open_root` devolve o incidente mais recente (`first_seen DESC`, `LIMIT 1`) que satisfaça todas as condições abaixo:
- `repeat_of_id IS NULL`;
- `status NOT IN ('resolved','closed')`;
- `deskmanager_ticket_id IS NOT NULL`;
- o mesmo `host_id` e o mesmo `trigger_id`;
- `lower(tags->>'ninf_customer_name') = lower(customer_name)`;
- `fingerprint <> fingerprint` do sinal atual.

Fluxo novo, só com a flag ligada, logo depois de `canonical_customer`:
1. `root = find_open_root(...)` numa sessão curta. Exceção → warning e `root = None`.
2. Sem `root`: o fluxo de hoje, sem mudança.
3. Com `root`:
   - `analyze_incident(..., skip="repeat")`; o registro da F1 grava `outcome="skipped_repeat"`;
   - **não** chama `ensure_glpi_ticket_serialized`;
   - se o incidente do sinal ainda não tem a tag `ninf_repeat_followup == "done"`, faz `glpi.add_comment(int(root.deskmanager_ticket_id), texto)` com `init_session`/`kill_session` no padrão do bloco do ticket;
   - o texto é escapado com `escape()`: `"Repetição do alerta: {host} — {trigger} (severidade {sev}, evento {event_id})"`.
   - Um erro do GLPI aqui vira `glpi_error`, com o mesmo tratamento de hoje: grava o incidente, relança e o Celery refaz.
   - Na persistência:
     - `repeat_of_id = root.id`;
     - `deskmanager_ticket_id` fica `None`;
     - tags `ninf_repeat_ticket_id = root.deskmanager_ticket_id`;
     - `ninf_repeat_followup = "done"`, só quando o comentário deu certo;
     - um `IncidentAction(action="repeat_followup", note=f"root={root.id} ticket={...}")`.
   - Para o Web Push, Loki e evento publicado, `ticket_id` é o da raiz.
   - `# ponytail:` uma queda entre o POST e o commit duplica um acompanhamento. O upgrade path é um marcador no texto e uma busca antes do POST.
   - `# ponytail:` se o webhook de solução do GLPI se perder, a raiz continua aberta no Hub e o acompanhamento vai para um chamado solucionado (o GLPI reabre ou ignora). O upgrade path é ler o status do ticket antes de comentar.

Em `resolve_ticket`, no mesmo commit que marca a raiz como `resolved`: as repetições com `repeat_of_id == incident.id` e `status != 'resolved'` passam a `resolved`, cada uma com um `IncidentAction(action="root_resolved", note=f"ticket={ticket_id}")`. O ack no Zabbix fica só na raiz, como hoje.

- [ ] **Step 1: testes que falham** (flag ligada por monkeypatch, salvo no último)
  - `test_repeat_same_host_trigger_is_followup`: o segundo evento faz 0 `create_ticket` e 1 `add_comment` no ticket da raiz. A repetição grava `repeat_of_id` e `deskmanager_ticket_id is None`, e a IA não é chamada (`outcome == "skipped_repeat"`).
  - `test_flapping_after_recovery_is_followup`: problema, recuperação da raiz e problema dão acompanhamento.
  - `test_resolved_root_opens_new_ticket`.
  - `test_root_without_ticket_is_not_reused`.
  - `test_repeat_never_crosses_customers`.
  - `test_other_trigger_same_host_opens_ticket`.
  - `test_repeat_retry_single_followup`: um GLPI 503 no comentário dá retry, e depois o total é 1 `add_comment`.
  - `test_root_lookup_failure_falls_back_to_ticket`: `find_open_root` levantando exceção mantém `create_ticket` chamado.
  - `test_resolve_root_resolves_repeats`.
  - `test_flag_off_keeps_ticket_per_event`.
  - A paridade de `REPEAT_SQL` vai em `test_bootstrap_sql.py`.
- [ ] **Step 2:** `pytest tests/test_alert_repeat.py -v` → FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** a suíte completa e `bash infra/tests/run-hub-local-flow.sh` → PASS. `test_alert_glpi_idempotency.py` fica verde sem mudança.
- [ ] **Step 5:** commit `feat: repetição do alerta Zabbix vira acompanhamento do chamado aberto`.

### Task 2: Medição de tempestade e fechamento

**Files:**
- Modify: `app/backend/app/api/routers/ai.py` (`/api/ai/metrics`)
- Modify: `app/frontend/src/components/AiView.tsx` (mais o tipo e o teste)
- Create: `docs/execution/ai-f2-tempestade.sql` (só leitura, para rodar em produção)
- Create: `docs/execution/ai-f2-aviso-operacao.md`
- Modify: `STATE.md`, a linha de estado da spec
- Test: `tests/test_ai_api.py`, o teste do `AiView`

**Interfaces:**
- Produces: `metrics["signals"] = {"signals": int, "tickets": int, "repeats": int, "ratio": float | None}`.
  - **signals:** incidentes com `created_at` na janela;
  - **tickets:** desses, os que têm `deskmanager_ticket_id`;
  - **repeats:** os que têm `repeat_of_id`;
  - **ratio:** `signals / tickets`, ou `None` quando `tickets == 0`.
  - O filtro de cliente e tenant é o mesmo das outras métricas: `lower(tags->>'ninf_customer_name')`.

`ai-f2-tempestade.sql`: uma consulta, só `SELECT`, nos últimos 30 dias de `n_infraops_incidents`. Por cliente, devolve:
- `incidents`: o total;
- `burst_10m`: incidentes que tiveram outro incidente do mesmo cliente nos 10 minutos anteriores (`EXISTS`);
- `same_host_30m`: o mesmo cálculo restrito ao mesmo `host_id` em 30 minutos;
- `repeat_same_trigger`: o mesmo cálculo com o mesmo `host_id` e o mesmo `trigger_id`, em qualquer intervalo, com a raiz ainda sem `glpi_resolved_at`.

A ordenação é por `burst_10m` decrescente. O cabeçalho do arquivo diz para que serve, como rodar (`psql -f`, conta só de leitura) e como ler: se `burst_10m` ficar perto de `incidents`, há tempestade e o investigador da F3 deve sugerir agrupamento; senão, a repetição basta.

- [ ] **Step 1: testes que falham**
  - `test_metrics_signals_ratio`: 5 incidentes, 2 com chamado e 2 repetições dão `ratio == 2.5` e `repeats == 2`; outro cliente fica fora com o filtro.
  - `test_metrics_signals_no_tickets_null`.
  - `test_storm_sql_runs`: executa o arquivo SQL contra o Postgres de teste depois de `run_migrations()` e verifica que não dá erro e que as colunas são as esperadas.
  - Frontend: o card "Sinais ÷ chamados" mostra `2,5`, com "2 repetições", e `null` vira `—`.
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** o CI completo → PASS.
- [ ] **Step 5: docs.**
  - Aviso à operação, curto e em português:
    - com `NINF_ZABBIX_REPEAT_FOLLOWUP_ENABLED=true`, o mesmo trigger no mesmo host com chamado aberto entra como acompanhamento;
    - o Web Push continua igual;
    - a solução no GLPI resolve a raiz e as repetições;
    - antes de ligar, rodar `ai-f2-tempestade.sql` e anexar o resultado.
  - `STATE.md`, Próximo passo: "promover F2 com a flag desligada; rodar a consulta de tempestade; ligar após aviso e OK do Ricardo; depois F3 (investigador do NOC)".
- [ ] **Step 6:** commit `docs: fecha F2 da IA nos chamados`.
