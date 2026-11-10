# ness.OS

**Tipo:** app

**Estágio:** em andamento

**Próximo passo:** Cutover do Zabbix em 14/11 23h (roteiro #225). Dados por cliente fechados (T1–T6, #199/#200/#207). UI espera o redesenho (Task 4 do plano de aceleração). Wazuh IaC mergeado (#204), `terraform apply` espera OK. Trilha: [plano de aceleração](docs/superpowers/plans/2026-11-05-acelerar-producao.md).

## Quadro (atualizado a cada task fechada)

Tasks do [plano de execução](docs/superpowers/plans/2026-10-26-ness-os-execution-plan.md).

### Feito
- Dados por cliente editáveis fechados (plano #195): T1 clientes e apelidos (#199), T2 regras de grupo de hosts (#200), T3 modalidade efetiva, T4 parâmetros de atendimento, T5 contatos do cliente (#200), T6 documentação e fechamento. Spec final em [contratos-sla-editaveis.md](docs/specs/contratos-sla-editaveis.md) com modelo, chaves, checklist de promoção e o que continua fora.
- Promoção `1346b06` (06/11, OK do Ricardo): contratos/SLA/calendário editáveis (#198), clientes e apelidos (#199), regras de grupo de hosts e contatos (#200); `promotion=PASS`, seeds conferidos (13 clientes, 22 apelidos, 3 políticas, 4 passos). Calendário comercial padrão 08–20; "sem cliente" = 720 min. Rollback: release `1175954`.
- Frontend com as telas Contratos e Clientes (#202) publicado em 06/11 (`ninf-frontend@sha256:c2c0953f…`); rollback pelos `.env` de `/opt/n-infraops/change-backups/frontend-20261106T135437/` (imagem anterior `f4afa04a…`).
- Dimensionamento do Wazuh R3a (#201): opção B aprovada para contratação (Contabo Cloud VPS 12, €25/mês c/ IVA, 24 meses); IaC em revisão (#204), **nada aplicado**; `terraform apply` pede novo OK.
- T09 GLPI (05/11): 949 incidentes abertos criados até 27/10 sem ticket marcados com a tag `sem_ticket_legado` (OK do Ricardo; `status` intacto; rollback pela lista de ids em `/opt/n-infraops/rollback/sem-ticket-legado/ids-2026-11-05.json`). Ticket automático nunca existiu para eles: sem replay
- 0.2 Limpeza da raiz — #100; CLI Contabo única em `app/cli/contabo` (estava quebrada sem `commands/`) — #105
- 0.1 Reconciliar estado — [evidência](docs/execution/evidence/state-reconciliation-2026-10-26.md)
- 0.3 CI — Actions religado; #81, #64 e #85 na `main`
- 0.4 Ferramental IaC (`infra/bin/tf`, `infra/bin/ansible`) — #89
- 1.1 Terraform importa as 3 VPS + Object Storage, `prevent_destroy`, guard de plano — #92 ; estado em `s3://ness-os-tfstate`, import aplicado, `plan` sem mudança — #104
- 1.2 Role `common` — #94; `--check` nos 3 hosts — #97 ([evidência](docs/execution/evidence/ansible-common-check-2026-10-27.md); aplicada nos 3 hosts em 27/10, re-check `changed=0`; root sem SSH na aiops — #106, #108, #109)
- 1.3 As-built gerado dos 3 hosts — #98
- 2.1 Matriz negativa GLPI T03 em lab, correção do gateway — #91
- 2.2 ADR 0020 aceito em 27/10 — #96, #110
- 2.3 GLPI T03 em produção em 28/10: gateway por digest, cliente API 1 desativado, 106 ativa com `[13, 1, 0]`, caminho direto Hub+106 **não** bloqueado — risco aceito no ADR 0020; plano: steps 3 e 4 ficam abertos — [evidência](docs/execution/evidence/glpi-t03-prod-2026-10-28.md)
- 2.4 GLPI T04: um ticket por alerta; 403 libera a reserva — #93
- 3.1 Frontend em `82ea3432` (#235: recargas do dashboard em rajada SSE viram uma só) desde 10/11, junto da API em `4a72949`.
- 3.1 Hub API + workers em `4a72949` desde 10/11 (#232: fecha a transação do SELECT de usuário, causa da queda de 24 min por `TooManyConnections`, #231; antes `69daf30` e `3b7e7cb` desde 05/11, com vínculo SOC #164, frescor #166, modalidade #167/#168; antes `9992bf7`: urgência/impacto #158, fila/timeline #161; antes `56c4659`, `521247b` em 30/10 e `7e7dfc6` em 28/10): monitor #111, alerta por e-mail #114, Unimed #115, LLM via OpenRouter #117, fundação SOC #122, idempotência do triage #125 — [evidência](docs/execution/evidence/hub-release-2026-10-26.md); promoção de 26/10 revertida (regressão GLPI, corrigida no #95); canário de alertas no script — #86
- 6.1 + 6.3 Testes do frontend (vitest) e isolamento do SSE — #90
- 6.2 Frescor/último sucesso/erro por fonte em `pipeline_health`, `ready` e exit code do monitor; UI sem hora falsa — #101
- Reconciliação dos alertas de 26–27/10: 739 sem ticket, 215 sem cobertura — #102
- 8.1 Contrato `AIRequestV1`, sanitização e métrica das chamadas ao Gemini — #99 (corrigiu vazamento de segredo para o Gemini em análise e triagem SOC); LLM via OpenRouter com limite de US$ 50/mês na chave — #117
- Fundação SOC (A1/A2/A5/A6 + [contrato de sinal v1](docs/specs/signal-contract-v1.md), #153; diagnóstico de agentes GLPI em #152) e idempotência de `/secops/triage` — #122, #125; em produção na release `521247b` (30/10, `promotion=PASS`, migração aplicada: `dedup_key`, índice único parcial, `customer_id` anulável). Não ativa Wazuh em produção; `n_infraops_tenant_mappings` ganhou os 9 vínculos `wazuh` em 03/11 (nada chama `/secops/triage` em produção ainda). Também: playbook do override do GLPI T03 — #124; `_resolve_tenant`, dedup concorrente e `pg_advisory_xact_lock` testados em Postgres real (service no CI) — #130
- Vínculos Wazuh → cliente cadastrados em 03/11 (9 grupos: `RZK-*` → `rzk`, `TARGET-*` → `target`, `TESTES-HARDENING` → `ness`) — [roteiro](infra/docs/runbooks/wazuh.md)
- T06 onda 1 (03/11): 5 ativos criados no GLPI (Computers 111–114, NetworkEquipment 157) — [evidência](docs/execution/evidence/glpi-t06-assets-2026-11-03.md); 498 vínculos de ticket criados nos mesmos 5 ativos (OK do Ricardo, readback ok, rollback pela lista de ids); 10997 → NetworkEquipment 158 (Nova Energia, entidade 9) com 11 vínculos. Pendente: modelo um-ativo-por-aparelho vs. por-link (158 duplica o 131). Seriais dos 2 Fortigates (157, 158) já gravados no GLPI
- Contratos e SLA editáveis (#198, em produção desde 06/11 e com tela no #202): prazos/calendários/escalonamento do P3 vêm de tabelas por contrato, com padrão interno NÃO contratual e API admin — [spec](docs/specs/contratos-sla-editaveis.md)
- 2.5 T05 GLPI: Computers 108–110 (entidade 1) criados e 1419 vínculos de ticket reparados (874 / 560 / 30), readback igual ao Hub, segunda aplicação 0; duas exceções `callAsSystem` aprovadas pelo Ricardo, só neste lote — [evidência](docs/execution/evidence/glpi-t05-assets-2026-11-02.md)
- 2.3b Isolamento Hub ↔ GLPI aplicado em 03/11 (#140): senhas do banco fora do `.env` do Hub (`/etc/ness-os/glpi-{db,app}.env`), `glpi-db` em rede interna própria, senhas rotacionadas; Hub sem a variável e sem resolver `glpi-db`. [Evidência](docs/execution/evidence/glpi-hub-isolation-2026-11-03.md)
- P0 Fundação SOC (03/11): atendimento por função própria, `pendente_de_cliente`, validação com campo/valor/sinal no log, prazo de 45 s no modelo, frequência persistida por tenant+cluster (`freq_key`). Em produção na release `56c4659` (04/11, `promotion=PASS`), coluna `freq_key` criada
- Backfill Zabbix → Hub aplicado em 04/11: 29.151 incidentes recuperados gravados, `status` intacto — [evidência](docs/execution/evidence/zabbix-hub-recovery-2026-11-03.md)
- P1 contrato de sinais v1 validado por consumidor independente (#160): `tenant_id` rejeitado na entrada, `severity_source.value` opcional, idempotência sem `tenant_id`
- P2 camada 1, primeiro corte só backend (#161): fila por prioridade, filtros, `ticket_state`, `/timeline`, `X-Request-ID`; Hub envia urgência/impacto ao GLPI (#158); prazos de resposta aceitos (#159)
- T08 diagnóstico do atendimento no GLPI (#156) e T07 preparo dos agentes: script com dry-run e rota `/Inventory` de exemplo (#157), nada aplicado em produção
- Recuperação Zabbix → Hub ligada em 03/11 (ação 7 e media type 72): antes nenhum incidente era marcado como recuperado. Frontend com o contador novo promovido em 04/11 (#149) — [evidência](docs/execution/evidence/zabbix-hub-recovery-2026-11-03.md)

### Em andamento
- Padrões operacionais aceitos em 09/11 (7 itens, internos, `contractual=false`; [folha](docs/specs/padroes-operacionais-propostos.md)). Já cadastrados: calendários e escalonamento `soc`→`noc`→`operator`→`admin` (4 passos, contrato 1). Revisor/dia da amostra e pausa do SLA não ganham campo agora (nada os consome; a pausa vive no GLPI). Faltam a escala de plantão real (fonte a definir) e feriados; fechamento automático no GLPI só com frase própria.
- Cutover do Zabbix (sábado 14/11 23h, #208 a #225): script de backup final (#219), ProxyOfflineBuffer (#221), SAML do Entra (#223, #224), roteiro final com pré-checagens de sexta (#225). Web pública desligada; restauração testada em 58 min (#222). Sem rollback possível após restaurar o banco no novo IP: o backup tem 23h59min59s de idade.
- Identidade: IdP do Hub configurável por ambiente (#211) para ligar o Entra ID ao Hub (antes só Authentik). ADR 0015 revisado (#209). Fase B (Entra, Cloudflare Access, desligar Authentik) só após o aceite do MVP.
- P3 backend (#210): caixa de avisos no frontend, ack e link da notificação abre o caso. Falta UI/PWA e escala de plantão real. **Teste de push pendente (10/11):** `n_infraops_push_subscriptions` = 0; o Edge do Ricardo falha no registro (`NotAllowedError: Registration failed - permission denied`) mesmo com a permissão do site em Permitir; o `GET /api/v1/push/config` responde 200 e o `POST …/subscribe` nunca chega. Retomar no Chrome/Firefox ou no celular; depois, frase "envia 1 push de teste". O e-mail de alerta segue ativo.
- Wazuh R3a: IaC mergeado (#204), `terraform apply` espera OK do Ricardo.
- Zabbix sem vínculo em `n_infraops_tenant_mappings`: fica `pendente_de_modalidade` até o Ricardo decidir o mapeamento cliente ↔ Zabbix

### Pronto para começar
- 2.5 T06 do plano GLPI (reconciliar todo o inventário)

### Esperando o Ricardo
0. Action1 ([ADR 0021](docs/adr/0021-action1-endpoint-executor.md)): API lida em GET (01/11, inventário e atualizações ausentes por organização OK); falta o mapa por endpoint e o resultado de execução, multi-tenant, licença acima de 200 endpoints e dados do agente antes de integrar; contratação precisa do seu OK
1. Replay dos 14 alertas ainda ativos sem ticket (Google Updater parado e disco em `alpdb01`/`alpdb02`)? Os 12 FortiGate já ganharam ticket; os 189 resolvidos ficam sem
2. Wazuh: limpar agentes desconectados (485, dos quais 146 há mais de 30 dias) e os 10 que nunca conectaram e apagar os scripts temporários da `homol`; regras 100100/100101 já aplicadas (`docs/execution/evidence/wazuh-rules-review-2026-10-29.md`)
3. Issue #82: valores achados recusados em aiops, Zabbix prod, UAT e nas APIs ([evidência](docs/execution/evidence/credenciais-82-2026-10-29.md)); **falta testar a `homol` do Wazuh** (só com `sudo`); decidir (a) desativar as 36 contas locais do GLPI que nunca logaram e (b) fechar o pedido ao GitHub Support dos refs de PR
4. Restringir a chave do agente à `stack` (`from=`)
6. Depois: D4 MFA, D3/D6 compras Psono/Wazuh

## Foco

- Escopo e decisões de produto: `docs/superpowers/plans/2026-10-12-ness-os-plano-master.md`.
- Estado factual: `docs/execution/ness-os-status.md`.
- Implantação em VPS nova depende de contratação aprovada pelo Ricardo; todo recurso nasce em `infra/terraform` e `infra/ansible`.
