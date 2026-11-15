# Regra de abertura de chamados — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chamado no GLPI só para problema que exige ação, um por problema, e sintomas de uma queda de link agrupados no chamado da causa.

**Architecture:** A ingestão (`process_alert_v1`) passa a só gravar o incidente, sem abrir chamado. Uma tarefa periódica (`decide_tickets`, a cada 60 s) aplica carência, lista de ação/ruído, causa→sintoma e dedup, e abre/comenta/reabre o chamado. O vínculo chave→chamado fica numa tabela do Hub (sem busca por marcador no GLPI). No Zabbix, um script aplica dependências "hosts do site dependem do FortiGate do site" a partir de um arquivo de topologia.

**Tech Stack:** Python 3.12, FastAPI, Celery (beat), SQLAlchemy async + Postgres, httpx (GLPI REST), Zabbix API 7.0, pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-regra-de-chamados-design.md`

## Global Constraints

- Carência padrão **15 min** (`ticket_grace_minutes`); janela de reabertura **24 h** (`ticket_reopen_hours`); janela de sintoma começa **2 min antes** da causa. Todos em `n_infraops_platform_params` (editáveis sem deploy).
- Chave de dedup: **cliente + host_id + trigger_id** (sha256 de `"{entity_id}:{host_id}:{trigger_id}"`).
- Correlação e dedup sempre dentro do **mesmo cliente** (entity_id). Nunca cruzar.
- Severidade 4–5 entra mesmo fora da lista de ação, **também** com carência.
- Site = segundo nível do grupo `[ Cliente ] [ Site ]` do host no Zabbix.
- Sem dependência nova (stdlib + o que já está instalado). Código em inglês, comentários e textos de chamado em português.
- Retry de GLPI existente (12 tentativas, backoff) continua; nenhuma decisão é perdida por falha do GLPI.
- Mudança no Zabbix de produção só com frase do Ricardo; script com simulação, `--apply` e `--rollback`.
- Validação: black 26.5.1, ruff (ordem de imports), pytest com `NINF_TEST_PG_URL`.

## Review Focus

1. **Host sem grupo de site** → nunca é sintoma; segue a regra 2 normalmente (teste na Task 5).
2. **GLPI fora durante a decisão** → incidente fica `pending`, decidido de novo no próximo ciclo, sem chamado duplicado (teste na Task 5).
3. **Recuperação antes da carência** → nenhum chamado (teste na Task 5).
4. **Mesmo nome de site em clientes diferentes** → causa do cliente A não suprime sintoma do cliente B (teste na Task 5).
5. **Regra com regex inválido na tabela** → ignorada com log; a decisão não quebra; severidade 4–5 ainda abre (teste na Task 2).

---

### Task 1: Esquema — regras, vínculos de chamado e parâmetros

**Files:**
- Create: `app/backend/sql/004_ticket_policy.sql`
- Modify: `app/backend/app/migrate.py` (executar o 004 logo após o 003, mesmo padrão `read_text`)
- Modify: `app/backend/sql/001_schema.sql` (incluir o mesmo conteúdo do 004 para bootstrap; o teste de paridade existente cobre)
- Modify: `app/backend/app/models/models.py` (modelos `TicketRule`, `TicketLink`)
- Test: `app/backend/tests/test_ticket_policy_schema.py`

**Interfaces:**
- Produces:
  - Tabela `n_infraops_ticket_rules(id serial pk, kind varchar(16) check in ('action','noise','cause'), pattern text not null, note text, enabled bool default true)`. Semeada com os padrões da spec (seção "Lista de ação" e "Nunca abre chamado"; `cause` = túnel caído, SD-WAN dead, link/interface down, Unavailable by ICMP de FortiGate). Regex POSIX case-insensitive (`~*`).
  - Tabela `n_infraops_ticket_links(entity_id int, dedup_key varchar(64), ticket_id int not null, state varchar(16) check in ('open','auto_closed','closed'), occurrences int default 1, last_seen timestamptz, closed_at timestamptz, primary key(entity_id, dedup_key))`.
  - Colunas novas em `n_infraops_incidents`: nenhuma. Estado da decisão vai em `tags`: `ninf_ticket_state` ∈ `pending|opened|attached|symptom|panel|skipped`, `ninf_site`, `ninf_cause_incident_id`, `ninf_grace_from` (ISO).
  - Índice `ix_incidents_ticket_pending` em `n_infraops_incidents ((tags->>'ninf_ticket_state')) where tags->>'ninf_ticket_state'='pending'`.
  - Params `ticket_grace_minutes=15`, `ticket_reopen_hours=24`, `ticket_symptom_lead_minutes=2` (insert on conflict do nothing).
  - Modelos `TicketRule`, `TicketLink` em `app.models`.

- [ ] **Step 1: Teste** `test_ticket_policy_tables_exist_and_seeded` (Postgres real): após `run_migrations()`, `select count(*) from n_infraops_ticket_rules where kind='noise'` > 0, idem `action` e `cause`; os 3 params existem com os valores acima; `n_infraops_ticket_links` aceita insert e rejeita `state='x'`.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Criar `004_ticket_policy.sql`, ligar no `migrate.py`, espelhar no `001_schema.sql`, modelos.
- [ ] **Step 4:** Rodar o teste e `tests/test_bootstrap_sql.py`; ambos passam.
- [ ] **Step 5:** Commit `feat: tabelas de regra e vínculo de chamado`.

### Task 2: Política pura — classificar, causa, site e chave

**Files:**
- Create: `app/backend/app/services/ticket_policy.py`
- Test: `app/backend/tests/test_ticket_policy.py`

**Interfaces:**
- Consumes: `TicketRule` (Task 1).
- Produces:
  - `@dataclass(frozen=True) class Rules: action: list[re.Pattern]; noise: list[re.Pattern]; cause: list[re.Pattern]`
  - `async def load_rules(session) -> Rules` — compila com `re.I`; padrão inválido é pulado com `logger.warning` (não levanta).
  - `def classify(title: str, severity: int, rules: Rules) -> Literal["action", "panel"]` — ruído vence tudo, **exceto** severidade ≥ 4; depois ação; senão `panel`.
  - `def is_cause(title: str, rules: Rules) -> bool`
  - `def site_from_hostgroups(groups: list[str]) -> str | None` — retorna o nome normalizado `"[ Cliente ] [ Site ]"` do primeiro grupo com exatamente dois níveis; aceita grupos aninhados (`[ A ] [ B ] [ C ]` → `[ A ] [ B ]`); `None` se não houver.
  - `def dedup_key(entity_id: int, host_id: str, trigger_id: str) -> str` — sha256 hex.

- [ ] **Step 1: Testes**
  - `classify('Windows: "GoogleUpdaterService157" ... is not running', 3, R) == "panel"`
  - `classify('FortiGate: VPN 17 Boticario: Tunnel down', 3, R) == "action"`
  - `classify('FortiGate: Unavailable by ICMP ping', 4, R) == "action"`
  - `classify('Windows: The Memory Pages/sec is too high', 4, R) == "action"` (sev ≥ 4 vence ruído)
  - `classify('Windows: The Memory Pages/sec is too high', 3, R) == "panel"`
  - `is_cause('FortiGate: SD-WAN [x]:[wan1]: Health check state is dead', R) is True`; `is_cause('Windows: High memory utilization', R) is False`
  - `site_from_hostgroups(['[ Unimed ]', '[ Unimed ] [ Itu ] [ Servidor V ]']) == '[ Unimed ] [ Itu ]'`; `site_from_hostgroups(['Templates']) is None`
  - `dedup_key(12,'1','2') != dedup_key(13,'1','2')`
  - `test_invalid_pattern_is_skipped`: `Rules` montado por `load_rules` com uma linha `pattern='('` não levanta e ignora a linha (Review Focus 5).
  - `R` = regras carregadas do seed da Task 1 (fixture Postgres) — garante que o seed cobre os exemplos reais.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar e ver passar.
- [ ] **Step 5:** Commit `feat: política de chamado (classificação, causa, site, chave)`.

### Task 3: GLPI — reabrir, solucionar e saber se há técnico

**Files:**
- Modify: `app/backend/app/integrations/glpi.py`
- Test: `app/backend/tests/test_glpi_ticket_lifecycle.py`

**Interfaces:**
- Produces (métodos de `GLPIClient`, mesmo padrão de erro `_glpi_failure`):
  - `async def has_technician(self, ticket_id: int) -> bool` — `GET Ticket/{id}/Ticket_User`, `True` se houver `type == 2`; ou qualquer `ITILFollowup` com `users_id` diferente do usuário da sessão.
  - `async def solve_ticket(self, ticket_id: int, content: str) -> None` — `POST ITILSolution` (`itemtype=Ticket`, `items_id`, `content`) e depois `PUT Ticket/{id}` com `status=5`.
  - `async def reopen_ticket(self, ticket_id: int, content: str) -> None` — `add_comment(..., private=False)` e `PUT Ticket/{id}` com `status=2`.

- [ ] **Step 1: Testes** com `httpx.MockTransport` (padrão de `tests/test_glpi_ticket_lookup.py`): `has_technician` true com `[{"type":2}]`, false com `[{"type":1}]` e sem follow-up humano; `solve_ticket` faz exatamente um POST em `/ITILSolution` e um PUT com `{"input":{"id":N,"status":5}}`; `reopen_ticket` faz POST em `/ITILFollowup` e PUT com `status=2`; 503 vira `GLPITransientError`.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar e ver passar.
- [ ] **Step 5:** Commit `feat: GLPI reabrir/solucionar chamado`.

### Task 4: Ingestão só grava; repetição comenta

**Files:**
- Modify: `app/backend/app/workers/alerts.py` (`_async_process_alert_v1`, `resolve_alert_customer`)
- Test: `app/backend/tests/test_alert_ingest_pending.py`
- Modify: `app/backend/tests/test_alert_glpi_idempotency.py` (testes que esperavam chamado na ingestão passam a mirar a Task 5)

**Interfaces:**
- Consumes: `site_from_hostgroups`, `dedup_key` (Task 2); `TicketLink` (Task 1).
- Produces:
  - `resolve_alert_customer(alert_data) -> tuple[str, str | None]` — agora devolve `(customer, site)`; o `host.get` já traz os hostgroups.
  - `_async_process_alert_v1` grava/atualiza o incidente com `tags.ninf_ticket_state="pending"`, `ninf_site`, `ninf_entity_id`, **sem** análise de IA e **sem** GLPI. Se já existe `TicketLink(state='open')` para a chave: `add_comment` "voltou a ocorrer às HH:MM (evento N)", `occurrences += 1`, `last_seen`, e o incidente fica `attached` com `deskmanager_ticket_id` do vínculo. Falha do GLPI nesse comentário segue o retry atual.
  - A análise de IA (`analyze_incident`) e o conteúdo do chamado passam para a Task 5 (só roda para quem vai virar chamado).
  - O push (`notify_tenant_stakeholders`) sai da ingestão e passa para a abertura do chamado (Task 5), com a mesma condição (HIGH/CRITICAL ou isolamento).

- [ ] **Step 1: Testes**
  - `test_problem_event_is_pending_without_glpi`: GLPI mockado sem chamadas; incidente com `ninf_ticket_state == "pending"` e `ninf_site == "[ Unimed ] [ Itu ]"`.
  - `test_recurrence_with_open_link_comments_once`: com `TicketLink(state='open', ticket_id=77)`, um novo `event_id` do mesmo host+gatilho gera exatamente um `add_comment(77, ...)`, `occurrences == 2`, incidente `attached`, nenhum `create_ticket`.
  - `test_recurrence_other_customer_not_attached`: mesmo host_id/trigger_id com outra entidade não usa o vínculo.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar a suíte de backend inteira; ajustar os testes antigos de idempotência para o novo ponto de abertura.
- [ ] **Step 5:** Commit `feat: ingestão grava incidente pendente e comenta repetição`.

### Task 5: Decisor periódico — carência, causa→sintoma, dedup e reabertura

**Files:**
- Create: `app/backend/app/workers/ticket_decider.py`
- Modify: `app/backend/app/workers/celery_app.py` (beat `decide-tickets`, 60 s, `app.workers.ticket_decider.decide_tickets`)
- Modify: `app/backend/app/workers/alerts.py` (expor `ensure_glpi_ticket_serialized` com a chave nova; ver abaixo)
- Test: `app/backend/tests/test_ticket_decider.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces:
  - `async def decide(now: datetime) -> dict[str, int]` (contagens por desfecho) e a task Celery `decide_tickets()` que chama `asyncio.run(decide(datetime.now(UTC)))`.
  - Reserva/lock: `ensure_glpi_ticket_serialized` passa a usar `dedup_key` no lugar do fingerprint do evento e grava `TicketLink(state='open')` na mesma transação da reserva. Sem `find_ticket_by_name_marker` no caminho normal.

**Algoritmo** (uma passada; lê só `ninf_ticket_state='pending'` e `ninf_zabbix_status='problem'`):
1. Carregar `Rules` e params.
2. **Causas primeiro:** pendentes com `is_cause` e `now - coalesce(ninf_grace_from, first_seen) >= grace` → abrir/reusar chamado (passo 5).
3. **Sintomas:** para cada pendente não-causa com `ninf_site`: se existe causa **ativa** (`ninf_zabbix_status='problem'`) do **mesmo `ninf_entity_id` e mesmo `ninf_site`** com `first_seen <= incidente.first_seen + lead` → estado `symptom`, `ninf_cause_incident_id`. Se a causa tem chamado, comentar nele a lista dos sintomas novos (um comentário por ciclo, não por sintoma).
4. **Demais pendentes** com carência vencida: `classify` → `panel` (estado `panel`, fim) ou `action` (passo 5).
5. **Abrir:** chave `dedup_key`. Se `TicketLink` `open` → comentar (`attached`). Se `auto_closed` e `closed_at >= now - reopen` → `reopen_ticket`, vínculo volta a `open`. Se `closed` (por técnico) ou fora da janela → chamado novo citando o anterior no texto. Senão chamado novo. A análise de IA e o push rodam só aqui.
6. Falha de GLPI num item → loga, deixa `pending`, segue os outros (o próximo ciclo tenta de novo; a reserva impede duplicata).

- [ ] **Step 1: Testes** (Postgres real, GLPI mock, `now` injetado):
  - `test_not_due_before_grace`: pendente com 14 min → sem chamado, continua `pending`.
  - `test_action_after_grace_opens_one_ticket`: túnel caído com 16 min → 1 `create_ticket`, `TicketLink(open)`, estado `opened`.
  - `test_noise_after_grace_is_panel`: Google Updater com 60 min → `panel`, zero chamadas GLPI.
  - `test_recovered_before_grace_never_tickets` (RF 3): `ninf_zabbix_status='resolved'` aos 10 min → não é lido; zero chamadas.
  - `test_symptom_suppressed_by_active_cause`: causa e 3 sintomas no mesmo cliente+site, sintomas começando de 1 min antes a 5 min depois → 1 chamado; sintomas `symptom`; 1 comentário listando os 3.
  - `test_symptom_waits_for_cause_decision`: sintoma com carência vencida e causa ainda na carência → sintoma `symptom`, sem chamado próprio.
  - `test_no_site_never_symptom` (RF 1): host sem `ninf_site` com causa ativa no mesmo cliente → segue regra 2.
  - `test_cause_other_customer_same_site_name` (RF 4): causa da entidade 12, sintoma da entidade 13 com o mesmo `ninf_site` → sintoma não é suprimido.
  - `test_reopen_within_24h`: vínculo `auto_closed` há 3 h → `reopen_ticket`, sem `create_ticket`.
  - `test_new_ticket_after_tech_close`: vínculo `closed` → `create_ticket` com o id anterior no conteúdo.
  - `test_glpi_down_keeps_pending_no_duplicate` (RF 2): 1ª passada com `create_ticket` levantando `GLPITransientError` → `pending`; 2ª passada com GLPI ok → exatamente 1 chamado no total.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar `ticket_decider.py` e o beat.
- [ ] **Step 4:** Rodar e ver passar; suíte inteira verde.
- [ ] **Step 5:** Commit `feat: decisor de chamados com carência, dedup e causa raiz`.

### Task 6: Recuperação — fechar chamado e liberar sintomas

**Files:**
- Modify: `app/backend/app/workers/alerts.py` (`_async_process_recovery`)
- Test: `app/backend/tests/test_ticket_recovery.py`

**Interfaces:**
- Consumes: `has_technician`, `solve_ticket` (Task 3); `TicketLink` (Task 1).
- Produces:
  - Incidente recuperado: `status='resolved'` no Hub (hoje fica `open`).
  - Se o incidente tem vínculo `open` e **todos** os incidentes ligados à chave estão recuperados: se `has_technician` → só comentário "resolvido na origem às HH:MM"; senão `solve_ticket(..., "Resolvido na origem (Zabbix) às HH:MM.")` e vínculo `auto_closed`, `closed_at=now`.
  - Se o incidente recuperado é **causa**: sintomas dele ainda `problem` voltam a `pending` com `ninf_grace_from = now` (carência conta da resolução da causa).

- [ ] **Step 1: Testes**
  - `test_recovery_auto_closes_untouched_ticket`: `has_technician=False` → 1 `solve_ticket`, vínculo `auto_closed`, incidente `resolved`.
  - `test_recovery_with_technician_only_comments`: `has_technician=True` → `add_comment`, sem `solve_ticket`, vínculo `open`.
  - `test_cause_recovery_releases_active_symptoms`: 2 sintomas, 1 já recuperado → só o ativo volta a `pending` com `ninf_grace_from` = horário da recuperação.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar e ver passar.
- [ ] **Step 5:** Commit `feat: recuperação fecha chamado e libera sintomas`.

### Task 7: Zabbix — topologia e dependências por site

**Files:**
- Create: `infra/scripts/zabbix-site-dependencies.py` (stdlib: `urllib`, `json`, `argparse`)
- Create: `infra/zabbix/topologia-sites.json` (gerado; revisado pelo Ismael)
- Create: `infra/tests/test_zabbix_site_dependencies.py` (unittest, sem rede)

**Interfaces:**
- Subcomandos: `generate` (lê grupos `[ C ] [ S ]` e hosts; grava o JSON), `plan` (lista o que criaria/removeria, padrão), `apply --site "<nome>" | --all`, `rollback [--site]`.
- Formato do JSON: `{"sites": [{"site": "[ Cliente ] [ Site ]", "gateways": ["<host>"...], "hosts": ["<host>"...], "revisado": false}]}`. Sites sem FortiGate entram com `gateways: []` e são pulados.
- Gatilho pai: o gatilho de disponibilidade do gateway (`Unavailable by ICMP ping` do template FortiGate). Com 2+ gateways: o Zabbix não tem "todos fora" nativo; o script cria no primeiro gateway um gatilho agregado `ness.OS: todos os gateways do site fora` (expressão AND sobre `icmpping` de cada gateway) e usa ele como pai.
- Dependência: em cada host do site, os gatilhos **não** de disponibilidade passam a depender do pai (`trigger.adddependencies`). Marca: tag `ness_os_dep=<site>` no gatilho agregado e registro local `infra/zabbix/aplicado-<data>.json` com os pares criados (usado no `rollback`).
- Execução: no servidor do Zabbix, API `http://127.0.0.1:8080/api_jsonrpc.php`, token de `/etc/ness-os/zabbix-cutover-bootstrap.env`; se o token não tiver escrita, `ZBX_TOKEN_FILE` aponta outro.

- [ ] **Step 1: Testes** com cliente de API falso: `generate` sobre grupos de exemplo produz um site com 1 gateway e um com 2; `plan` para 2 gateways inclui o gatilho agregado; `rollback` remove exatamente os pares do registro; site com `gateways: []` não gera nada.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar e ver passar; `generate` real (só leitura) no servidor novo e commit do JSON gerado.
- [ ] **Step 5:** Commit `feat: script de dependências por site no Zabbix`.

### Task 8: Entrega em produção (depois do D+2, com frase)

Sem código. Roteiro em `docs/runbooks/regra-de-chamados-rollout.md`:

- [ ] **Step 1:** Promover a API (junto com a promoção pós-D+2), `migrate.py` cria tabelas e params. Antes: backup do banco do Hub.
- [ ] **Step 2:** Pendentes antigos: marcar os incidentes `open` anteriores ao deploy como `ninf_ticket_state='skipped'` (um `UPDATE` com backup), para o decisor não processar o passado.
- [ ] **Step 3:** Observar 24 h: chamados/dia (`select count(*) from n_infraops_ticket_links where ...`), `panel` vs `opened` vs `symptom`, erros do worker. Meta: < 60/dia.
- [ ] **Step 4:** Ismael revisa `topologia-sites.json`; `apply --site` em um site (frase do Ricardo), observar uma queda real ou simulada; depois `--all`.
- [ ] **Step 5:** Rollback documentado: voltar a imagem anterior da API (o caminho antigo abre por evento) e `zabbix-site-dependencies.py rollback`.

---

**Fora deste plano** (spec: passo separado): desligar no Zabbix os gatilhos de serviço de atualização do Windows.

**Decisão de construção:** a spec cita `topologia-sites.yml`; o plano usa **JSON** para o script ficar só com stdlib no servidor do Zabbix.
