# GLPI como mesa do técnico + alertas por grupo — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer do GLPI a mesa do técnico e entregar os alertas do Hub pelo grupo do GLPI. Cobre as fases G1, G2, A1 e G3 da spec.

**Architecture:**
- Parte fixa do GLPI por **um script PHP idempotente**, no padrão de `infra/scripts/glpi-operations-foundation.php`: lê um plano em JSON, roda em simulação por padrão e só grava com `--apply`.
- Pessoas, equipes e plantão são **cadastrados no Hub**, e o prazo vem dos contratos que já existem no Hub;, que reconcilia o GLPI (o Hub é a fonte; o GLPI não é editado à mão).
- Limpeza por script separado, com backup antes.
- No Hub, só o necessário:
  - o destinatário do aviso passa a vir do grupo do chamado;
  - o chamado é aberto com resumo e link;
  - o decisor liga chamados NOC↔SOC.

**Tech Stack:** GLPI 11.0.8 (PHP, modelos internos), FastAPI/SQLAlchemy async, pytest com Postgres de teste.

**Spec:** `docs/superpowers/specs/2026-11-24-glpi-alertas-paineis-design.md`

**Fora deste plano:** A2, P1 e P2 (alertas ao gestor do cliente e painéis). Ganham plano próprio depois de G1 a A1 estarem em produção, porque dependem do prazo já vindo do GLPI.

## Global Constraints

- Produção exige frase do Esper. A configuração (Task 1) e a limpeza (Task 2) pedem frases separadas.
- Backup do banco do GLPI antes de qualquer `--apply`: `mysqldump` dentro de `ninf-glpi-db`, gravado em `/opt/n-infraops/change-backups/glpi-<UTC>`.
- As notificações do GLPI ficam desligadas (`use_notifications=0`). O script aborta se encontrar o valor 1.
- Técnico externo: perfil limitado à própria entidade e sem permissão de configuração. Só Cavan e Alupar.
- Nada de segredo em log ou commit. Nada de nome de cliente em fixture: usar `acme`.
- Horários exibidos em America/Sao_Paulo.

## Review Focus

1. **Entidade com subentidades** (Alupar, Alupar CO, Alupar PE): a atribuição cai no grupo da entidade do chamado, nunca no da mãe. Teste na Task 1b, em `desired_state` com as 3 entidades.
2. **Chamado sem grupo atribuído** (entidade nova): o aviso vai para o plantão e nunca para ninguém. Teste na Task 3.
3. **Edição manual no GLPI:** membro incluído à mão é removido na reconciliação e reportado. Teste na Task 1b.
4. **GLPI fora do ar durante a reconciliação:** falha fechada, sem gravação parcial, e estado "erro" na tela. Teste na Task 1b.
5. **Chamado já tocado por humano na limpeza:** nunca é resolvido em massa. Teste na Task 2.

---

### Task 1: Base fixa do GLPI (G1, parte fixa)

O que **não** é cadastro: árvore de categorias, perfil Técnico externo, grupo Plantão e regras-base. Pessoas e equipes **não** entram aqui (ver Task 1b).

**Files:**
- Sem JSON: são 3 categorias e 6 regras fixas, verificadas por id e nome no próprio script.
- Categorias: a 4 vira `NOC` e a 5 vira `SOC`, ambas na raiz; a 1 vira `Serviço`. As subcategorias acompanham, e os ids 4 e 24, que o Hub usa, são preservados. Não há migração de chamado.
- Create: `infra/scripts/glpi-g1-base.php`, no padrão de `glpi-operations-foundation.php`: simulação por padrão, `--apply` para gravar.
- Modify: `infra/docs/runbooks/glpi.md` (seção "Mesa do técnico": aplicar e reverter).

**Interfaces:**
- Produz: o grupo `ness · Plantão`, o perfil `Técnico externo` e as categorias-raiz `NOC`, `SOC` e `Serviço`. A Task 1b procura esses três por nome.
- Desliga as 4 regras "SLA - Assign Bronze/Silver/Gold/Platinum" e as 8 SLAs soltas. Elas estão quebradas: `definition_time` vazio, sem SLM e prazo por prioridade, não por cliente. A Task 1b recria o SLA a partir dos contratos.

- [ ] **Step 1:** Escrever o JSON.
- [ ] **Step 2:** Escrever o script. Ele:
  - aborta se `use_notifications=1`;
  - migra os chamados das categorias antigas e nunca exclui categoria;
  - arquiva os 18 grupos de área vazios com `is_assign=0` e um comentário.
- [ ] **Step 3:** Rodar a simulação em produção (só leitura). Esperado: só `CREATE` ou `UPDATE`, sem erro.
- [ ] **Step 4:** Com a frase do Esper: backup, depois `--apply` duas vezes. Esperado na 2ª rodada: só `OK`.
- [ ] **Step 5:** Commit `feat: base fixa do GLPI (categorias, perfil externo, plantão)`.

### Task 1b: Pessoas e equipes no Hub, refletidas no GLPI (G1, cadastro)

O Hub é o único cadastro de pessoas e equipes **[Esper, 24/11]**. Ninguém mexe nisso à mão no GLPI. Hoje o Hub não tem tela nem API de usuários (eles nascem por seed ou SQL). Esta task cria as duas coisas.

**Files:**
- Create: `app/backend/sql/005_teams.sql`
- Modify: `app/backend/app/models/models.py` (`TeamMember`)
- Modify: `app/backend/app/models/users.py` (`User.is_oncall`, `User.glpi_user_id`)
- Create: `app/backend/app/api/routers/people.py`
- Create: `app/backend/app/services/glpi_team_sync.py`
- Modify: `app/backend/app/integrations/glpi.py` (métodos de escrita de usuário, grupo e regra)
- Modify: `app/backend/app/workers/tasks.py` (agendar a reconciliação)
- Create: `app/frontend/src/components/PeopleScreen.tsx` e entrada em Administração
- Test: `app/backend/tests/test_people.py`, `app/backend/tests/test_glpi_team_sync.py`

**Interfaces:**
- SQL:
  - `ALTER TABLE n_infraops_users ADD is_oncall BOOLEAN NOT NULL DEFAULT FALSE, ADD glpi_user_id INTEGER`;
  - `CREATE TABLE n_infraops_team_members (customer_id BIGINT NOT NULL, user_id BIGINT NOT NULL, PRIMARY KEY (customer_id, user_id))`.
- API (`/api/people`, só `admin` e `platform_admin`):
  - `GET /api/people` → lista com `{id, email, full_name, kind, customers[], is_oncall, is_active, glpi_sync}`;
  - `POST /api/people` com `{email, full_name, kind: "ness"|"externo", customer_ids[], is_oncall}`:
    - cria o `User`; `kind=ness` → papel `noc`; `kind=externo` → papel `cliente` com `tenant_id` igual à `key` do único cliente;
    - envia convite de senha pelo fluxo de e-mail já existente;
  - `PUT /api/people/{id}` para alterar equipes ou plantão; `DELETE` desativa, não apaga.
- `services/glpi_team_sync.py`:
  - `desired_state(session) -> GlpiDesired`: função pura sobre o banco que descreve grupos, membros, perfis, regras e SLA por entidade. O SLA vem do contrato que já existe no Hub (`n_infraops_contracts` + `n_infraops_sla_policies`): por cliente, um SLM no GLPI com TTO/TTR por severidade, e uma regra entidade + prioridade → SLA;
  - `async reconcile(glpi, desired, apply: bool) -> list[str]`: diferenças no formato `"CREATE user x"`, `"ADD x→ness · Cavan"`, `"FIX rule …"`.
- Nome do grupo: `ness · <Customer.display_name>`. A regra de atribuição é `entities_id = Customer.glpi_entity_id → grupo`.

**Validação na fronteira:**
- `externo` exige exatamente 1 cliente.
- O e-mail é normalizado para minúsculas e precisa ser único.
- Um externo não pode ser plantão.
- Cliente sem `glpi_entity_id` não aceita equipe (422).

- [ ] **Step 1: Testes da API** (`test_people.py`):
  - `test_externo_requires_exactly_one_customer` → 422 com 0 ou 2 clientes;
  - `test_externo_cannot_be_oncall` → 422;
  - `test_externo_gets_cliente_role_and_tenant`: papel `cliente`, `tenant_id == "acme"`;
  - `test_only_admin_manages_people`: papel `noc` recebe 403;
  - `test_delete_deactivates_and_bumps_session_epoch`: `is_active=False` e `session_epoch` incrementado.
- [ ] **Step 2: Testes da reconciliação** (`test_glpi_team_sync.py`), com GLPI falso em memória:
  - `test_new_member_creates_user_and_membership`;
  - `test_external_gets_external_profile_only_on_own_entity`;
  - `test_manual_glpi_extra_member_is_removed_and_reported`: o diff contém `REMOVE`;
  - `test_deactivated_user_removed_from_groups_and_disabled_not_deleted`;
  - `test_second_run_is_noop`: diff vazio;
  - `test_glpi_down_raises_and_changes_nothing`: falha fechada, sem escrita parcial (Review Focus 4).
- [ ] **Step 3:** Rodar e ver falhar.
- [ ] **Step 4:** Implementar:
  - a reconciliação roda depois de cada `POST`/`PUT`/`DELETE`, em tarefa assíncrona, e a cada 15 min no worker;
  - a resposta da API traz `glpi_sync: "pendente"|"ok"|"erro"`, e a tela mostra esse estado;
  - criar usuário no GLPI usa o login igual ao e-mail, sem senha local (entra por SSO ou pela redefinição do próprio GLPI).
- [ ] **Step 5:** Escrever a tela `PeopleScreen` (DS 2.0.1, kit `nx-*`):
  - lista de pessoas com tipo, clientes, plantão e estado da sincronização;
  - formulário de criação e edição;
- [ ] **Step 6:** Rodar a suíte completa com Postgres e `npm test` no frontend.
- [ ] **Step 7:** PR, merge e promoção, com a frase do Esper. Depois, o Esper cadastra as equipes pela tela, e a reconciliação em simulação mostra o diff antes da 1ª gravação.
- [ ] **Step 8:** Fazer um chamado sintético por entidade e conferir o grupo e `slas_id_ttr > 0`. Entrar como externo da Cavan e ver só a Cavan. Excluir os sintéticos.

### Task 2: Limpeza do acumulado e fechamento automático (G2)

**Files:**
- Create: `infra/scripts/glpi_backlog_bulk_solve.py` (roda no contêiner da API, no padrão de `glpi_backlog_reconcile.py`)
- Test: `app/backend/tests/test_glpi_backlog_bulk_solve.py`

**Interfaces:**
- Consome: `GLPIClient.has_technician(ticket_id) -> bool` e `GLPIClient.solve_ticket(ticket_id, content) -> None` (`app/integrations/glpi.py:526,534`).
- Produz: `select_candidates(rows: list[dict], cutoff: datetime) -> list[int]`. Função pura que recebe linhas `{id, date, has_tech, has_human_followup, hub_state}`.

- [ ] **Step 1: Teste**

```python
def test_select_candidates():
    cutoff = datetime(2026, 11, 23, 3, tzinfo=timezone.utc)
    old = {"date": cutoff - timedelta(days=1), "has_tech": False, "has_human_followup": False, "hub_state": None}
    rows = [
        {"id": 1, **old},
        {"id": 2, **old, "has_tech": True},
        {"id": 3, **old, "has_human_followup": True},
        {"id": 4, **old, "date": cutoff + timedelta(hours=1)},
        {"id": 5, **old, "date": cutoff + timedelta(hours=1), "hub_state": "panel"},
        {"id": 6, **old, "date": cutoff + timedelta(hours=1), "hub_state": "resolved"},
    ]
    assert select_candidates(rows, cutoff) == [1, 5, 6]
```

- [ ] **Step 2:** Rodar e ver falhar: `pytest tests/test_glpi_backlog_bulk_solve.py -q`.
- [ ] **Step 3:** Implementar `select_candidates`. O resto do script tem as seguintes regras:
  - lê os chamados com status 1 direto pela API do GLPI, em lotes de 200;
  - por padrão só conta e só resolve com `--apply`;
  - a solução registrada é "Encerrado na limpeza de 24/11: alerta antigo sem ação técnica.";
  - o log mostra só contagens.
- [ ] **Step 4:** Rodar e ver passar.
- [ ] **Step 5:** Investigar por que `n_infraops_ticket_links` tem 0 `auto_closed`, se `alerts.py:762` já resolve sozinho. Possível causa: o webhook de recuperação do Zabbix não chega a esse ramo. Corrigir na camada certa, com teste em `tests/test_alerts*.py` que simule a recuperação de um chamado sem técnico e espere `state == "auto_closed"`.
- [ ] **Step 6:** Com a frase do Esper:
  - backup (Global Constraints);
  - rodar a contagem e mostrar o número ao Esper;
  - rodar com `--apply`.

  Esperado: chamados com status 1 na casa das dezenas.
- [ ] **Step 7:** Commit `feat: limpeza do acumulado do GLPI e fechamento automático`.

### Task 3: Aviso pela equipe do cliente (A1)

Como o Hub é dono das equipes, o destinatário sai do banco do Hub. O aviso não lê o GLPI.

**Files:**
- Modify: `app/backend/app/services/notifications.py` (`_recipients`)
- Test: `app/backend/tests/test_notifications.py`

**Interfaces:**
- Consome: `n_infraops_team_members` e `User.is_oncall` (Task 1b).
- Produz: `_recipients(session, inc, step) -> list[User]`, que exclui sempre o papel `cliente` (o A2 cuida desse papel):
  - passo 0: membros ativos da equipe do cliente do incidente; se não houver, o plantão;
  - passo 1: plantão;
  - passo 2+: `admin` e `platform_admin`.

- [ ] **Step 1: Testes**
  - `test_step0_goes_to_customer_team`;
  - `test_no_team_falls_back_to_oncall` (Review Focus 2);
  - `test_cliente_role_never_receives_technician_alert`;
  - `test_other_customer_team_not_notified`;
  - `test_step2_goes_to_management`.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar. O cliente do incidente vem de `tags.ninf_customer_name` → `Customer.key` (como em `services/customers.py`).
- [ ] **Step 4:** Rodar a suíte completa.
- [ ] **Step 5:** PR e merge. A promoção junta esta task e o #290 e pede a frase do Esper.

### Task 4: Conteúdo do chamado e ligação NOC↔SOC (G3)

**Files:**
- Modify: `app/backend/app/workers/ticket_decider.py` (`_alert_data`, depois de `_open`)
- Modify: `app/backend/app/integrations/glpi.py` (novo método)
- Modify: `app/backend/app/api/routers/secops.py` (nível ≥ 12 → incidente pendente do ramo SOC)
- Test: `app/backend/tests/test_ticket_decider.py`, `tests/test_secops*.py`

**Interfaces:**
- Produz: `GLPIClient.link_tickets(a: int, b: int) -> None` (`Ticket_Ticket`, `link=1`, "relacionado").
- Produz: o parâmetro `ticket_cross_link_minutes` em `n_infraops_ticket_rules`/`ticket_policy.DEFAULTS`, com valor 30.
- Produz: a tag `ninf_branch` com valor `noc` ou `soc` no incidente. Zabbix → `noc`; Wazuh → `soc`.

- [ ] **Step 1: Testes**
  - `test_ticket_body_has_summary_and_link`: o corpo do chamado contém `ver no ness.OS` e `https://hub.ness.com.br/?view=incidents&id=<id>`, e não contém o nome do servidor Zabbix nem do Wazuh;
  - `test_cross_branch_linked_within_window`: chamado NOC e chamado SOC abertos com 10 min de diferença, do mesmo cliente e da mesma máquina; espera-se que `link_tickets` seja chamado uma vez e que haja um acompanhamento em cada chamado;
  - `test_cross_branch_not_linked_outside_window`: 45 min de diferença; espera-se nenhuma ligação;
  - `test_same_branch_never_cross_linked`: dois chamados NOC; espera-se nenhuma ligação, porque a dedup já cuida desse caso;
  - `test_wazuh_level12_creates_pending_incident`: alerta do Wazuh com nível 12 cria incidente com `ninf_ticket_state="pending"` e `ninf_branch="soc"`; nível 10 continua só registrando.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar. A ligação NOC↔SOC usa a máquina (`host_name`) ou, se não houver, o site (`ninf_site`). Ela roda logo depois de `_open`, na mesma passada do decisor.
- [ ] **Step 4:** Rodar a suíte completa.
- [ ] **Step 5:** PR e merge. A promoção precisa da frase do Esper. Depois da promoção:
  - medir, em 24 h, quantos chamados o ramo SOC abriu;
  - se passar de 50 por dia, subir o limiar para 13 em `n_infraops_ticket_rules`, sem novo deploy.
- [ ] **Step 6:** Escrever na base de conhecimento do GLPI o procedimento "RDP vindo de loopback" (categoria `SOC/Acesso suspeito`). É conteúdo e não código, mas é o primeiro procedimento da spec §4.5.

---

**Ordem de execução:** Task 1 → Task 1b → Task 2 → Task 3 → Task 4. A Task 1b depende da base da Task 1; a Task 3, das equipes da 1b. A Task 2 vem depois da 1 porque a limpeza deve rodar com as categorias já migradas.
