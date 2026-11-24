# GLPI como mesa do técnico + alertas por grupo — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer do GLPI a mesa do técnico e entregar os alertas do Hub pelo grupo do GLPI. Cobre as fases G1, G2, A1 e G3 da spec.

**Architecture:**
- Configuração do GLPI por **um script PHP idempotente**, no padrão de `infra/scripts/glpi-operations-foundation.php`: lê um plano em JSON, roda em simulação por padrão e só grava com `--apply`.
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

1. **Entidade com subentidades** (Alupar, Alupar CO, Alupar PE): a atribuição deve cair no grupo da entidade do chamado, não no grupo da entidade-mãe. Teste na Task 1 (simulação com as 3).
2. **Chamado sem grupo atribuído** (entidade nova): o aviso vai para o plantão e nunca para ninguém. Teste na Task 3.
3. **Usuário do Hub sem par no GLPI** (e-mail diferente): não recebe aviso de grupo, e o caso é registrado em log sem e-mail. Teste na Task 3.
4. **Reexecução do script de configuração:** a segunda rodada de `--apply` não cria nem altera nada (0 mudanças). Teste na Task 1.
5. **Chamado já tocado por humano na limpeza:** nunca é resolvido em massa. Teste na Task 2.

---

### Task 1: Configuração do GLPI (G1)

**Files:**
- Create: `infra/glpi/plano-g1.json` (grupos, membros, plantão, árvore de categorias, regras)
- Create: `infra/scripts/glpi-g1-mesa-tecnico.php`
- Modify: `infra/docs/runbooks/glpi.md` (seção "Mesa do técnico": aplicar, reverter)

**Interfaces:**
- Produz: grupos com o nome `ness · <Entidade>` e `ness · Plantão`, com `is_assign=1`. O nome é a chave lida pelo Hub na Task 3.
- Produz: o perfil `Técnico externo`.
- Produz: as categorias-raiz `NOC`, `SOC` e `Serviço`.

**Dado de entrada que falta (bloqueia o `--apply`, não a escrita):** pedir ao Esper:
- quais técnicos da ness atendem cada cliente;
- quem fica no plantão;
- os usuários externos da Cavan e da Alupar.

- [ ] **Step 1:** Escrever `plano-g1.json` com o seguinte conteúdo:
  - `groups[]`: `{entity, name, members[]}`, um por entidade;
  - `oncall`: `{name:"ness · Plantão", members[], recursive:true}`;
  - `external_profile`: derivado de `Technician`, sem `config`, `rule_*`, `profile` nem `entity` e com `ticket` restrito;
  - `categories`: mapa da categoria atual para `NOC/…`, `SOC/…` ou `Serviço/…`, cobrindo as 29 categorias;
  - `rules`:
    - uma regra de atribuição por entidade: entidade = X → grupo atribuído = `ness · X`;
    - uma regra de reserva: sem grupo → Plantão;
    - "Route to NOC/SOC" passam a só definir a categoria;
  - `sla_tier`: mapa entidade → Bronze/Silver/Gold/Platinum.
- [ ] **Step 2:** Escrever o script. Comportamento:
  - em simulação, imprime `CREATE`, `UPDATE` ou `OK` por objeto;
  - aborta se `use_notifications=1`;
  - migra os chamados das categorias antigas antes de arquivá-las e nunca exclui categoria;
  - arquiva os 18 grupos de área vazios com `is_assign=0` e um comentário, sem excluí-los;
  - corrige as condições das 4 regras de SLA para casar com o campo de tier da entidade.
- [ ] **Step 3:** Rodar a simulação no GLPI de produção (só leitura). Esperado: só `CREATE` ou `UPDATE`, nenhum erro, e as 3 entidades Alupar com grupos distintos.
- [ ] **Step 4:** Com a frase do Esper, fazer o backup e rodar `--apply`. Depois, rodar `--apply` de novo. Esperado na segunda rodada: só `OK`.
- [ ] **Step 5:** Fazer um chamado sintético por entidade, pela API e em nome do usuário de integração. Conferir:
  - grupo atribuído correto;
  - `slas_id_ttr > 0`.

  Depois, excluir os chamados sintéticos.
- [ ] **Step 6:** Entrar como usuário externo da Cavan e listar chamados. Esperado: só a entidade Cavan.
- [ ] **Step 7:** Commit `feat: GLPI como mesa do técnico (grupos, plantão, categorias, SLA)`.

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

### Task 3: Aviso pelo grupo do GLPI (A1)

**Files:**
- Modify: `app/backend/app/services/notifications.py` (`_recipients`, `sweep`)
- Modify: `app/backend/app/integrations/glpi.py` (novo método)
- Test: `app/backend/tests/test_notifications.py`

**Interfaces:**
- Consome: o nome de grupo `ness · <Entidade>` e `ness · Plantão` (Task 1).
- Produz: `GLPIClient.ticket_group_emails(ticket_id: int) -> list[str]`, que retorna os e-mails dos membros dos grupos atribuídos (`Group_Ticket` com type 2 → `Group_User` → `UserEmail`).
- Produz: `_recipients(session, inc, step, group_emails: list[str], oncall_emails: list[str]) -> list[User]`, com a seguinte regra:
  - passo 0: usuários ativos do Hub cujo e-mail está em `group_emails`; se a lista estiver vazia, os de `oncall_emails`;
  - passo 1: plantão;
  - passo 2+: papéis de gestão (`admin` e `platform_admin`).

- [ ] **Step 1: Testes** em `test_notifications.py`, com `ticket_group_emails` mockado:
  - `test_step0_goes_to_ticket_group`: o grupo tem `u0`; espera-se aviso só para `u0`;
  - `test_no_group_falls_back_to_oncall`: o grupo vem vazio e o plantão tem `u1`; espera-se aviso só para `u1`;
  - `test_hub_user_without_glpi_match_not_notified`: o e-mail do grupo não existe no Hub; espera-se `notified == 0` e um log `recipient_unmatched`;
  - `test_cliente_never_receives_technician_alert`: um usuário com papel `cliente` está no grupo; espera-se que ele não receba o aviso de técnico, porque A2 cuida do cliente.
- [ ] **Step 2:** Rodar e ver falhar.
- [ ] **Step 3:** Implementar. Os e-mails do grupo são lidos uma vez por incidente e por varredura. Se o GLPI estiver fora do ar, a varredura deve falhar fechada: não avisa naquele ciclo e registra em log. Não pode haver fallback para "todos".
- [ ] **Step 4:** Rodar a suíte completa com Postgres. Esperado: tudo passa.
- [ ] **Step 5:** PR, checks, threads, merge. A promoção junta esta task e o #290 e precisa da frase do Esper.

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

**Ordem de execução:** Task 1 → Task 2 → Task 3 → Task 4. A Task 3 depende dos nomes de grupo da Task 1. A Task 2 vem depois da 1 porque a limpeza deve rodar com as categorias já migradas.
