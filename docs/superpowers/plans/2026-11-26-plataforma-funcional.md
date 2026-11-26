# Plataforma funcional: fechamento dos gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar a plataforma funcional ponta a ponta: técnico trabalha no GLPI, alerta chega ao celular, cliente vê o próprio painel e recebe resumo, e tudo que Esper quer ajustar é editável sem deploy.

**Architecture:** Nada de serviço novo. Cada gap fecha com coluna aditiva, tarefa do Celery já existente (beat), endpoint FastAPI no padrão atual e uma seção de tela. O que muda dado no GLPI ou no Cloudflare é script idempotente com `--apply`.

**Tech Stack:** FastAPI + SQLAlchemy async, Celery beat (`America/Sao_Paulo`), Postgres, React/Vite (oxlint, vitest), PHP do GLPI para script, Resend (e-mail) e Web Push (VAPID) já configurados em produção.

**Spec:** `docs/superpowers/specs/2026-11-24-glpi-alertas-paineis-design.md` (fases G1 a P2; este plano fecha A2, Prazo e o que o desenho deixou fora). Plano anterior: `2026-11-24-glpi-alertas-g1-a1.md`.

## Global Constraints

- Cliente externo: só leitura, só o próprio tenant (`tenant_id` = `key` do cliente); nunca o perfil `noc`.
- Texto e dado para o cliente nunca citam ferramenta, servidor ou pessoa da ness.; o único nome de produto é `ness.OS`.
- Horários sempre em Brasília (`America/Sao_Paulo`).
- Resumo ao gestor: **diário simples, semanal completo**, nunca um e-mail por evento (decisão de Esper, 26/11).
- Tempos e regras editáveis fora do código: `platform_params` (só `platform_admin` escreve; NOC lê). SLA em minutos fica no GLPI.
- Mudança em produção só com frase explícita de Esper. Migração só aditiva (`ADD COLUMN IF NOT EXISTS`, sem `;` dentro de comentário SQL).
- DS 2.0.1: acento `#00ADE8`, raio 0, sem gradiente, sem exclamação, `ness.OS` escrito assim.
- Backend verde antes de PR: `ruff check app/`, `ruff format --check app/`, `black --check .`, `mypy app/ --ignore-missing-imports`, pytest com `NINF_TEST_PG_URL`. Frontend: `npx tsc --noEmit`, `npx vitest run`, `npm run lint`.

## Review Focus

- Gestor com `summary_recipient` mas sem chamado aberto: o diário não envia e-mail vazio (teste `test_daily_skips_when_nothing_open`).
- Dois gestores no mesmo cliente e um em outro: cada um só recebe o próprio tenant (`test_summary_never_crosses_tenant`).
- Texto do resumo com nome de ferramenta ou servidor: nunca sai (`test_summary_has_no_forbidden_names`).
- Regex inválida ou catastrófica em regra de chamado: a API recusa e o decisor continua rodando (`test_rule_rejects_invalid_regex`).
- Resend desligado ou falhando: o resumo registra falha e tenta no ciclo seguinte sem duplicar o do dia (`test_summary_idempotent_per_day`).

## Onde estamos contra o pedido

| Necessidade | Estado | Tarefa |
|---|---|---|
| Técnico registra e resolve no GLPI, um grupo por cliente, plantão vê tudo | Pronto | n/a |
| Alerta no celular para técnico e plantão | Pronto (A1) | n/a |
| Alerta e resumo ao gestor do cliente (A2) | **Falta** | 2 |
| Painel por cliente (ness e cliente) | Pronto (P1, P2); bloco Prazo falta | 6 |
| Hub como cadastro único, sem retrabalho no GLPI | Quase: sync falha ao dar perfil externo; conta duplicada do Fabrizio | 0 |
| Tempos e regras editáveis, nada fixo | API dos tempos pronta (#310); falta tela e CRUD de regras | 1 |
| Promoção repetível | API sim; frontend é troca manual | 3 |
| Documentação e STATE em dia | Defasada desde 25/11 | 3 |
| Vigilância do volume do SOC e da reconciliação | Manual | 4 |
| Horário de silêncio e "meus avisos" (spec §5) | Falta | 5 |
| Governança no painel do cliente | Aguarda Esper | 7 |

---

### Task 0: Higiene de acesso (bloqueia o uso real por externos)

**Files:**
- Create: `infra/scripts/glpi-profile-sync-rights.php`
- Modify: `infra/docs/runbooks/glpi.md`

**Interfaces:**
- Produces: perfil GLPI `ness.OS Hub Sync` (id 17) com os direitos do perfil "Técnico externo" (id 14), para o `sync_glpi_team` conceder o perfil sem passo manual.

- [ ] **Step 1: Conta duplicada do Fabrizio.** `fabrizio.vieira` (GLPI id 20) e `ffviera` (id 110) são a mesma pessoa. O id 20 é Technician na entidade 0 **recursivo**: vê todos os clientes. Com a frase "desative o fabrizio.vieira antigo" de Esper, desativar o id 20 e remover o perfil. Verificar: `select is_active from glpi_users where id=20` retorna 0.
- [ ] **Step 2: Escrever `glpi-profile-sync-rights.php`** (padrão do `glpi-sla-base.php`: sem `--apply` só mostra, idempotente, nunca apaga) que copia para o perfil 17 os direitos de `glpi_profilerights` do perfil 14 que faltam.
- [ ] **Step 3: Rodar sem `--apply`** e conferir a lista de direitos (esperado: 41 a mais, todos de interface do técnico externo). Com a frase de Esper ("libere o perfil de sync"), rodar com `--apply`.
- [ ] **Step 4: Teste de aceite.** Cadastrar um externo sintético pelo Hub (`@example.com`, cliente de teste), esperar o ciclo de 15 min e conferir `glpi_profiles_users` com `profiles_id=14`; desativar o sintético. Esperado: diff do sync 0 sem inserção manual.
- [ ] **Step 5: Primeiro acesso real.** Com Ismael, Elidevaldo e Fabrizio abrem o Hub, Ismael vincula em "Logins pendentes". Verificar que o código por e-mail (PIN) também abre o GLPI para eles; registrar o resultado no runbook.
- [ ] **Step 6: Commit** `docs: perfil de sync do GLPI com direitos do técnico externo`.

### Task 1: Tela de tempos e regras de chamado

**Files:**
- Create: `app/backend/app/api/routers/ticket_rules.py`; `app/backend/tests/test_ticket_rules_api.py`
- Modify: `app/backend/app/main.py` (registrar router); `app/frontend/src/components/contracts/PolicyEditors.tsx` (duas seções); `app/frontend/src/hooks/useContracts.ts`

**Interfaces:**
- Consumes: `PUT /platform-params/{key}` e `GET /platform-params` (#310); `TicketRule(kind, pattern, note, enabled)`.
- Produces: `GET /api/ticket-rules -> list[{id, kind, pattern, note, enabled}]` (NOC); `POST /api/ticket-rules {kind, pattern, note}` (`platform_admin`); `PATCH /api/ticket-rules/{id} {enabled}`; `DELETE /api/ticket-rules/{id}`.

- [ ] **Step 1: Testes** em `test_ticket_rules_api.py`: `test_rule_rejects_invalid_regex` (422 para `"("`), `test_rule_rejects_unknown_kind` (422), `test_rule_duplicate_409`, `test_rule_write_needs_platform_admin` (403 para `noc`), `test_rule_listed_for_noc` (200).
- [ ] **Step 2: Rodar e ver falhar** (`pytest tests/test_ticket_rules_api.py -q`; falha por rota inexistente).
- [ ] **Step 3: Implementar o router.** Validar com `re.compile(pattern, re.I)`; limite de 200 caracteres no padrão; log `ticket_rule_change` com usuário (mesmo formato de `platform_param_change`).
- [ ] **Step 4: Teste passa.** Mesmo comando; esperado: 5 passed.
- [ ] **Step 5: Frontend.** Seção "Tempos do decisor" (cinco parâmetros, valor atual, padrão, máximo, salvar) e seção "Regras" (lista por tipo, adicionar, ligar e desligar). Só `platform_admin` vê os botões. Teste vitest: botão de salvar ausente para `noc`.
- [ ] **Step 6: PR, `@codex review`, merge.** Promoção junto do #310 e do que mais estiver no lote.
- [ ] **Step 7 (depois de promovido, com a frase de Esper):** cadastrar `VM3DService.*is not running` como ruído pela tela (é a maior fonte de chamado sem ação: 24 em 7 dias).

### Task 2: A2, aviso e resumo ao gestor do cliente

**Files:**
- Create: `app/backend/app/services/client_summary.py`; `app/backend/app/workers/summaries.py`; `app/backend/tests/test_client_summary.py`
- Modify: `app/backend/app/models/users.py` (coluna); `app/backend/app/migrate.py` (ALTER aditivo); `app/backend/app/api/routers/people.py` (`PersonIn`, `PersonPatch`, `_out`); `app/backend/app/api/routers/painel.py` (extrair função); `app/backend/app/services/notifications.py` (`tier`); `app/backend/app/workers/celery_app.py` (beat); `app/frontend/src/components/people/PeopleView.tsx` (marcação)

**Interfaces:**
- Produces: `User.summary_recipient: bool` (default false; só faz sentido com `role=cliente`; API recusa em `ness`); `async def painel_dados(db: AsyncSession, scope: str) -> dict` extraída de `painel()` sem mudar a resposta; `async def build_summary(db, customer_key: str, kind: Literal["diario","semanal"], now: datetime) -> tuple[str, str] | None` (assunto e texto; `None` quando o diário não tem nada aberto); `async def send_summaries(kind, now) -> dict[str, int]` (`sent`, `skipped`, `failed`); tarefas `app.workers.summaries.send_daily` (todo dia 08:00 Brasília) e `send_weekly` (segunda 08:00 Brasília).

- [ ] **Step 1: Testes** em `test_client_summary.py`: `test_daily_skips_when_nothing_open`, `test_summary_never_crosses_tenant`, `test_summary_has_no_forbidden_names` (o texto não contém `zabbix`, `wazuh`, `glpi`, `rzk-01`, `pool-01`, nem e-mail `@ness.com.br`), `test_summary_idempotent_per_day` (segunda chamada no mesmo dia não reenvia), `test_weekly_contains_all_panel_blocks`. E-mail do Resend simulado por stub de `ResendEmailClient.send`.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Migração e modelo.** `ALTER TABLE n_infraops_users ADD COLUMN IF NOT EXISTS summary_recipient BOOLEAN NOT NULL DEFAULT false`. Expor na tela Pessoas (caixa "Recebe o resumo") e na API de pessoas, restrito a externo.
- [ ] **Step 4: Extrair `painel_dados`** e reaproveitar em `build_summary`. O diário traz abertos por ramo (NOC/SOC), os que passaram do prazo quando o bloco Prazo existir e o que ficou "aguardando você"; o semanal traz os blocos do painel. Idempotência por dia: tag no Redis `summary:<kind>:<customer>:<yyyymmdd>` com expiração de 26 h, gravada só depois de o Resend aceitar.
- [ ] **Step 5: Beat** com `crontab(hour=8, minute=0)` e `crontab(day_of_week=1, hour=8, minute=0)`, fila `alerts.primary`.
- [ ] **Step 6: Push ao gestor.** Em `_recipients.tier`, o `cliente` com `summary_recipient` e tenant igual ao do caso deixa de ser excluído quando há técnico externo na equipe. Teste: `test_manager_gets_push_for_own_tenant_only`.
- [ ] **Step 7: Testes passam, CI local verde, PR, `@codex review`, merge.**
- [ ] **Step 8: Aceite em produção (com a frase de Esper):** marcar um destinatário de teste, forçar `send_daily` uma vez e conferir que o e-mail chega só com dado da Cavan.

### Task 3: Promoção repetível e documentação em dia

**Files:**
- Create: `infra/scripts/aiops-promote-hub-frontend.sh`
- Modify: `docs/runbooks/promocao-hub.md`; `infra/docs/runbooks/glpi.md`; `STATE.md`; `docs/superpowers/plans/2026-11-24-glpi-alertas-g1-a1.md` (Task 2b)

**Interfaces:**
- Produces: `aiops-promote-hub-frontend.sh <sha40> <frontend-ref@sha256> [--dry-run]`; ao fim imprime `frontend_image=<ref>` e `hub_http=200`.

- [ ] **Step 1: Script.** Backup de `.env` em `/opt/n-infraops/app` e em `releases/<sha40>/app` (`*.bak-fe`), troca de `NINF_FRONTEND_IMAGE`, `docker compose -p app -f docker-compose.yml -f docker-compose.tickets.yml up -d --no-deps frontend` **a partir da pasta da release** (o compose que vale), confere `docker inspect` e `hub=200`; se falhar, restaura o `.env` e recria o contêiner. `--dry-run` só imprime os passos.
- [ ] **Step 2: Verificação.** `bash -n infra/scripts/aiops-promote-hub-frontend.sh` sem saída e `--dry-run` listando os cinco passos.
- [ ] **Step 3: `promocao-hub.md`:** trocar a nota de frontend manual por este script e registrar que a promoção da API não troca o frontend.
- [ ] **Step 4: `glpi.md`:** SLA por tipo de atuação, limpeza em lote, sub-entidades da RZK, perfil externo e o direito do perfil de sync (Task 0), onde editar os tempos (Task 1).
- [ ] **Step 5: Guia Cloudflare Access** (sem segredo): política "externos (e-mail individual)", como acrescentar um e-mail, como reverter; guardar o backup fora de `/tmp`.
- [ ] **Step 6: `STATE.md`** com estágio, o que está em produção (#292 a #310) e o próximo passo em uma frase. Task 2b do plano antigo reescrita para o que foi feito.
- [ ] **Step 7: PR `docs:`, merge.**

### Task 4: Vigilância automática do que hoje é manual

**Files:**
- Modify: `app/backend/app/workers/zabbix_reconcile.py`; `app/backend/app/workers/ticket_decider.py`; `app/backend/app/services/policy_params.py` (um parâmetro novo `soc_ticket_alert_threshold`, padrão 50, e `reconcile_stale_alert`, padrão 100); `app/backend/tests/test_ticket_policy.py`

**Interfaces:**
- Produces: aviso por push aos usuários `is_oncall` quando (a) chamados SOC abertos em 24 h passam de `soc_ticket_alert_threshold` ou (b) incidentes velhos que a reconciliação não consegue recuperar passam de `reconcile_stale_alert` por mais de 1 h. Uma vez por dia por tipo.

- [ ] **Step 1: Testes:** `test_soc_volume_alert_once_per_day` e `test_reconcile_stale_alert_threshold`.
- [ ] **Step 2: Falha, implementar, passa.** O aviso só avisa: ajustar `soc_ticket_min_level` continua sendo decisão de Esper pela tela da Task 1.
- [ ] **Step 3: PR e merge.**

### Task 5: Horário de silêncio e "meus avisos"

**Files:**
- Create: `app/backend/app/api/routers/avisos.py`; `app/backend/tests/test_avisos.py`
- Modify: `app/backend/app/migrate.py` (tabela `n_infraops_user_prefs`); `app/backend/app/services/notifications.py` (`_notify`); `app/frontend/src/App.tsx` e um componente `AvisosView.tsx`

**Interfaces:**
- Produces: `GET/PUT /api/me/avisos` com `{quiet_start: int|None, quiet_end: int|None, mute_push: bool, mute_email: bool}` (horas 0–23, Brasília). `_notify` pula push e e-mail dentro do silêncio, **exceto** quando `User.is_oncall`.

- [ ] **Step 1: Testes:** `test_quiet_hours_skip_push`, `test_oncall_ignores_quiet_hours`, `test_quiet_window_crossing_midnight`.
- [ ] **Step 2: Falha, implementar, passa.** O aviso pulado fica como pendente e entra no próximo ciclo depois do silêncio; não se perde.
- [ ] **Step 3: Tela mínima** com os quatro campos, acessível a todo papel (inclusive `cliente`). Teste vitest de renderização.
- [ ] **Step 4: PR e merge.**

### Task 6: Bloco Prazo (bloqueado até haver ~30 dias de chamados com SLA, cerca de 26/12)

**Files:**
- Modify: `app/backend/app/integrations/glpi.py`; `app/backend/app/api/routers/painel.py`; `app/frontend/src/components/PainelView.tsx`; `app/backend/app/migrate.py` (`n_infraops_customers.show_prazo BOOLEAN NOT NULL DEFAULT false`)
- Test: `app/backend/tests/test_painel_prazo.py`

**Interfaces:**
- Produces: `GLPIClient.sla_tickets(entity_id: int, since: datetime) -> list[dict]` (chamados com `time_to_own`, `time_to_resolve`, `takeintoaccountdate`, `solvedate`); no painel, `prazo: {mes_pct: float|None, tendencia_90d: list[{semana: str, pct: float}]}` só quando `show_prazo` é verdadeiro, senão ausente.

- [ ] **Step 1: Teste** `test_prazo_absent_when_flag_off` e `test_prazo_percent_counts_only_slaed_tickets` (chamado sem SLA não entra na conta).
- [ ] **Step 2: Falha, implementar, passa.**
- [ ] **Step 3: Aviso "prazo perto de vencer"** ao técnico do grupo quando falta menos de 20% do tempo; reaproveita `sla_tickets` e o canal de push de A1. Teste `test_near_due_push_once_per_ticket`.
- [ ] **Step 4: Ligar por cliente** pela tela de clientes; Esper decide quando e para quem. Começa desligado para todos.

### Task 7: Governança no painel do cliente (bloqueada por Esper)

Nada a construir antes de Esper definir o que o bloco mostra. Perguntas que destravam, na ordem: (1) quais referências (normas, controles, prazos de certificação)? (2) de onde vem o dado (cadastro manual no Hub ou outro sistema)? (3) o cliente vê tudo ou só o resumo? Quando responder, entra como bloco `governanca` no `painel_dados` e na tela, com teste de que a visão `cliente` não recebe nome de pessoa da ness.

---

## Ordem de execução e portas

1. **Task 0** hoje (depende de duas frases de Esper e do Ismael).
2. **Task 1 e Task 3** em seguida, no mesmo lote de promoção com o #310.
3. **Task 2** logo depois (a decisão de diário e semanal já foi dada).
4. **Task 4 e Task 5** quando 1 a 3 estiverem em produção.
5. **Task 6** a partir de 26/12; **Task 7** quando Esper detalhar.

**Fora do código (donos):** Ismael instala o Atera em lote (RZK Agro, 237 máquinas) e migra `WIN-PRD-DB`, `WHRZKDTC01` e os 2 Linux da RZK Sol; Esper revoga o token da Cloudflare ao fim do Access e fornece a chave do Action1 quando a homologação (ADR 0021) começar; Hostinger segue adiada.

## Self-review

- **Cobertura da spec:** A2 (Task 2), Prazo (6), "meus avisos" e silêncio (5), grupo e perfil externo (0), tempos editáveis (1), governança (7). P1, P2, G1 a G3 e A1 já estão em produção.
- **Consistência de tipos:** `painel_dados` é definida na Task 2 e consumida na Task 6; `summary_recipient` aparece só na Task 2; chaves de parâmetro novas só em `policy_params.py`, com o teste de defaults atualizado junto.
- **Proporção:** uma tarefa por entrega que um revisor poderia rejeitar sozinha; nenhum corpo de função no plano.
