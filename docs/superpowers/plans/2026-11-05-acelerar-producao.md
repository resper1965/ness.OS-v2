# Acelerar a produção plena Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cortar o caminho crítico até o MVP em produção de ~4 semanas para ~2, removendo esperas e serialização que não são técnicas.

**Architecture:** O tempo não está no código (CI ~90 s, merge em minutos, promoção ~40 min). Está em quatro esperas: decisões do Ricardo, HTML do redesenho, contratação do Wazuh e filas seriais de PR. O plano ataca cada uma: decisões viram padrões aceitos por omissão, a UI avança sem bloquear a lógica, a contratação começa já em paralelo e as faixas de trabalho passam a ser paralelas onde os arquivos não colidem.

**Tech Stack:** o existente (FastAPI, React/Vite, PWA já presente em `app/frontend/public/{manifest.json,sw.js}` e `PushNotificationToggle.tsx`, Terraform/Ansible, GitHub Actions). Nada novo.

**Spec:** `docs/superpowers/plans/2026-11-04-trilha-de-execucao.md`, `docs/superpowers/plans/2026-11-05-dados-por-cliente-editaveis.md`, plano do Ricardo `ness-os-plano-por-projeto.md` (somente leitura).

## Global Constraints

- Produção só muda com a frase explícita do Ricardo, dito o efeito. Padrão aceito por omissão vale para **configuração e dado interno marcado `contractual=false`**, nunca para promoção, `UPDATE` em produção, custo recorrente ou Entra/DNS/Caddy/Cloudflare.
- Nenhum valor contratual inventado: padrão interno sempre marcado não contratual.
- Custo recorrente novo (VPS Wazuh) exige OK do Ricardo; toda VPS nasce em `infra/terraform` + `infra/ansible` + doc.
- Restrição do encaminhamento: UI da fila e da cobertura espera o redesenho (`ness-os-encaminhamento-dev.md`, linha 32). Este plano **não a quebra**: a Task 4 só avança com liberação dita pelo Ricardo.
- Fase B de identidade (Entra, Cloudflare Access, desligar Authentik) só após o aceite do MVP.
- PR de código: revisor Sonnet + Codex tratado antes do merge. Sem framework novo.
- Fuso `America/Sao_Paulo`.

## Review Focus

- Padrão aceito por omissão vira "contratual" por engano: toda leitura da API devolve `contractual=false` enquanto não houver contrato ativo; teste pina isso (Task 1).
- Promoções diárias empilham risco: cada uma segue com rollback pronto e canário; um lote com falha não bloqueia o seguinte (Task 5).
- Push ligado sem chave VAPID em produção: o toggle da UI falha em silêncio; o smoke da Task 3 tem de provar a entrega, não só o `200` da assinatura.
- Faixas paralelas colidem em `migrate.py`/`001_schema.sql`: uma faixa por vez toca esses arquivos (Task 2).
- Contratação do Wazuh sem desenho de coleta compra capacidade errada: Task 6 entrega o dimensionamento do R3a antes do pedido de compra.

## Onde o tempo realmente vai (medido)

| Etapa | Duração | Dá para cortar? |
|---|---|---|
| CI de um PR | 50–100 s | não precisa |
| Espera do Codex por PR | 3–5 min | sim: enviar PRs em lote e revisar em paralelo |
| Promoção da API | 25–50 min (backup ~10, canário 5, ciclo) | sim: pré-aquecer o backup, uma promoção por dia |
| Esperar resposta do Ricardo por item | horas a dias | **maior ganho**: padrões aceitos por omissão |
| HTML do redesenho | indefinido | bloqueio externo; Task 4 |
| Contratação do Wazuh | indefinido | começar já, em paralelo; Task 6 |
| Fila serial T1→T2→T5→T3→T4 | 4 autores em sequência | parcial; Task 2 |

---

### Task 1: Folha de padrões aceitos por omissão (remove ~70% das esperas)

**Files:**
- Create: `docs/specs/padroes-operacionais-propostos.md`
- Modify: `STATE.md` (uma linha)

**Interfaces:**
- Produces: tabela `item | padrão proposto | onde é editável | se o Ricardo não responder em 24 h`. Cada linha pode ser sobrescrita depois pela tela de contratos; nenhuma é contratual.

- [ ] **Step 1:** Escrever a tabela com estes itens e padrões (todos editáveis, `contractual=false`): revisor da amostra semanal = papel `soc` de plantão, segunda-feira 09:00 BRT; calendário padrão 24x7 para severidade 4 e 5 e 08–18 BRT dias úteis para o resto, feriados nacionais do ano; escalonamento 50/80/100% do prazo; pausa do SLA só em "Pendente" com motivo aprovado; fechamento Solucionado→Fechado em 7 dias com reabertura; janela OT retrospectiva de 24 h (teto da política); plantão = ordem atual por papel `soc/noc/operator/admin` até haver fonte de escala real.
- [ ] **Step 2:** Mandar ao Ricardo **uma** mensagem com a tabela e a pergunta única: "Aceita estes padrões internos, editáveis depois por contrato? (sim/não por linha)".
- [ ] **Step 3:** Com "sim", gravar os padrões como seed do PR de contratos (`is_default`, `contractual=false`) e marcar a linha no `STATE.md`. Sem resposta em 24 h: seguir com o seed só em ambiente de teste e **não** promover.
- [ ] **Step 4: Commit** `docs: padrões operacionais propostos`.

### Task 2: Faixas paralelas sem colisão

**Files:**
- Modify: `.superpowers/sdd/2026-11-05-dados-por-cliente-editaveis/progress.md` (ledger, fora do Git)

**Interfaces:**
- Produces: três faixas, cada uma com dono e arquivos disjuntos.

- [ ] **Step 1:** Fixar as faixas: **Faixa A (backend de dados)** = T1 → T2+T5 no mesmo PR → contratos → T3 → T4 (única que toca `migrate.py`, `001_schema.sql`, `models.py`); **Faixa B (frontend/PWA)** = Tasks 3 e 4 (só `app/frontend`); **Faixa C (infra/docs)** = Tasks 5 e 6 (só `infra/`, `docs/`).
- [ ] **Step 2:** Juntar T2 e T5 num único autor e PR (hoje 2 PRs, 2 revisões, 2 esperas do Codex): menos um ciclo completo.
- [ ] **Step 3:** Despachar as faixas B e C agora, em paralelo com a A. Verificação: `git diff --name-only` de cada branch não cruza com as outras faixas.

### Task 3: Provar o push agora (PWA já existe)

**Files:**
- Modify: `app/frontend/src/components/PushNotificationToggle.tsx` (só se o smoke achar defeito)
- Test: `app/frontend/src/components/PushNotificationToggle.test.tsx` (se não existir)

**Interfaces:**
- Consumes: `POST /api/push/subscribe` existente, `sweep_notifications`.
- Produces: evidência de entrega real de um push de teste a uma assinatura do Ricardo.

- [ ] **Step 1:** Conferir em produção, só leitura, se `NINF_VAPID_PUBLIC_KEY`/`PRIVATE` estão definidas no `.env` (sem imprimir o valor) e se `/manifest.json` e `/sw.js` respondem 200 em `hub.ness.com.br`.
- [ ] **Step 2:** Pedir ao Ricardo **uma ação**: abrir `hub.ness.com.br`, ativar o aviso no navegador e responder "ativado". Conferir só a contagem em `n_infraops_push_subscriptions`.
- [ ] **Step 3:** `sweep_notifications` não serve para um push isolado: seleciona até 50 incidentes abertos e envia e-mail e push a cada destinatário (`services/notifications.py:228,279-290`). Por isso, antes do teste, criar um caminho dirigido: `python -m app.services.push_test --user <id>` (ou endpoint `platform_admin` `POST /api/push/test`) que envia **uma** mensagem fixa ao próprio usuário autenticado, sem tocar incidentes nem e-mail. Teste: `test_push_test_sends_single_message_and_no_email`. Só então pedir a frase para executá-lo uma vez; esperado: o Ricardo confirma o recebimento.
- [ ] **Step 4:** Se o toggle falhar, teste `test_toggle_reports_failure_when_vapid_missing` (mostra erro visível em vez de silêncio) e correção mínima. Commit `fix: toggle de push mostra falha`.

### Task 4: UI sem esperar o HTML (condicionada à liberação)

**Files:**
- Create/Modify: `app/frontend/src/components/` (fila, contratos), só depois da liberação

**Interfaces:**
- Consumes: `/api/incidents` (fila/timeline), `/api/customers`, `/api/contracts` (PRs da Faixa A).
- Produces: telas funcionais no padrão `ness-design` (BlueDot `#00ADE8`, raio 0, Lucide 1.5, sem gradiente/sombra) que o redesenho substitui só na camada visual.

- [ ] **Step 1:** Perguntar ao Ricardo, em uma frase: "Posso construir fila e tela de contratos agora no padrão ness-design e trocar o visual quando o seu HTML chegar? (recomendo sim)". Sem "sim", **esta task não começa**.
- [ ] **Step 2:** Com "sim": carregar a skill `ness-design`; separar lógica (hooks e chamadas à API) de apresentação, de modo que o redesenho troque só os componentes de apresentação.
- [ ] **Step 3:** Testes vitest por tela: `test_queue_orders_by_priority`, `test_contract_form_blocks_viewer`, `test_no_vendor_name_in_ui`.
- [ ] **Step 4:** UAT incremental: cada tela entregue entra numa lista de aceite curta para o Ricardo, em vez de um UAT único no fim.

### Task 5: Trem de promoção diário

**Files:**
- Modify: `docs/runbooks/promocao-hub.md` (criar se não existir), `infra/scripts/aiops-promote-hub-api.sh` (somente se o pré-aquecimento exigir)

**Interfaces:**
- Produces: rotina de uma promoção por dia com um lote de PRs, backup pré-aquecido.

- [ ] **Step 1:** Documentar a rotina: o script exige backup com **menos de 30 min** (`aiops-promote-hub-api.sh:23-33`) e inicia outro se não houver, então não existe pré-aquecimento antecipado: o ganho real é **escolher o horário** (fora do backup noturno) e **juntar o lote**. Lote de PRs mergeados até 14:00 vai numa só promoção, disparada logo depois do corte; resultado e rollback registrados em `hub-release-2026-10-26.md`.
- [ ] **Step 2:** Cada promoção do dia continua pedindo a frase do Ricardo dita com o efeito. Mensagem-modelo: "Promover `<sha>` (tabelas aditivas X, API Y). Rollback `<release>`. Diga **promove**".
- [ ] **Step 3:** Verificação: duas promoções consecutivas em dias diferentes com `promotion=PASS` e `ready=200`.

### Task 6: Contratação do Wazuh em paralelo

**Files:**
- Create: `docs/specs/wazuh-r3a-dimensionamento.md`, depois `infra/terraform/` (módulo) e `infra/ansible/` (role), só após o OK de custo

**Interfaces:**
- Produces: dimensionamento do R3a single-node (agentes, eventos/s, retenção, disco, RAM, vCPU) e custo mensal estimado, para o Ricardo aprovar.

- [ ] **Step 1:** Levantar na `homol` (somente leitura, `ness_ro`) agentes ativos, eventos/s, tamanho do índice e retenção atual.
- [ ] **Step 2:** Escrever o doc com a configuração recomendada, o preço de tabela do provedor e a pergunta única: "Autoriza contratar a VPS do Wazuh nesta configuração? (sim/não)".
- [ ] **Step 3:** Com "sim": módulo Terraform + role Ansible + doc, `terraform plan` sem mudança além da VPS nova, aplicação só com OK dito. Sem "sim": não escrever IaC.
- [ ] **Step 4: Commit** `docs: dimensionamento do Wazuh R3a`.

---

## Efeito esperado (estimativa minha, não medida)

| Antes | Depois |
|---|---|
| MVP em ~3–4 semanas (1–5 dez) | ~2 semanas (≈ 20 nov) se Task 1 e Task 4 forem liberadas em até 2 dias |
| Wazuh começa depois de tudo | começa em paralelo; chegada depende do provedor |
| 1 UAT no fim | UAT por tela |

## Self-Review

- **Cobertura:** as quatro esperas medidas têm tarefa (decisões=1, filas=2, redesenho=4, Wazuh=6); a promoção=5; o push que já existe=3.
- **Consistência:** os nomes de tabelas/APIs vêm do plano de dados por cliente; nenhuma assinatura nova aqui.
- **Limite honesto:** o ganho de 2 semanas só vale se o Ricardo responder às Tasks 1, 4 e 6; sem isso o prazo não muda. A contratação depende do provedor, que não controlo.
- **Proporção:** plano menor que o plano de dados; sem corpos de código.
