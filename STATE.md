# ness.OS

**Tipo:** app

**Estágio:** em andamento

**Próximo passo:** P2 camada 1 (backend) fechada e em produção; a UI espera o HTML do redesenho (P6). Seguir no P3 (consumidor do bearer do gateway). O produtor v1 do Wazuh espera contratação e desenho de coleta (D3/D6). Trilha: [plano de 04/11](docs/superpowers/plans/2026-11-04-trilha-de-execucao.md).

## Quadro (atualizado a cada task fechada)

Tasks do [plano de execução](docs/superpowers/plans/2026-10-26-ness-os-execution-plan.md).

### Feito
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
- 3.1 Hub API + workers em `3b7e7cb` desde 05/11 (vínculo SOC #164, frescor #166, modalidade #167/#168; antes `9992bf7`: urgência/impacto #158, fila/timeline #161; antes `56c4659`, `521247b` em 30/10 e `7e7dfc6` em 28/10): monitor #111, alerta por e-mail #114, Unimed #115, LLM via OpenRouter #117, fundação SOC #122, idempotência do triage #125 — [evidência](docs/execution/evidence/hub-release-2026-10-26.md); promoção de 26/10 revertida (regressão GLPI, corrigida no #95); canário de alertas no script — #86
- 6.1 + 6.3 Testes do frontend (vitest) e isolamento do SSE — #90
- 6.2 Frescor/último sucesso/erro por fonte em `pipeline_health`, `ready` e exit code do monitor; UI sem hora falsa — #101
- Reconciliação dos alertas de 26–27/10: 739 sem ticket, 215 sem cobertura — #102
- 8.1 Contrato `AIRequestV1`, sanitização e métrica das chamadas ao Gemini — #99 (corrigiu vazamento de segredo para o Gemini em análise e triagem SOC); LLM via OpenRouter com limite de US$ 50/mês na chave — #117
- Fundação SOC (A1/A2/A5/A6 + [contrato de sinal v1](docs/specs/signal-contract-v1.md), #153; diagnóstico de agentes GLPI em #152) e idempotência de `/secops/triage` — #122, #125; em produção na release `521247b` (30/10, `promotion=PASS`, migração aplicada: `dedup_key`, índice único parcial, `customer_id` anulável). Não ativa Wazuh em produção; `n_infraops_tenant_mappings` ganhou os 9 vínculos `wazuh` em 03/11 (nada chama `/secops/triage` em produção ainda). Também: playbook do override do GLPI T03 — #124; `_resolve_tenant`, dedup concorrente e `pg_advisory_xact_lock` testados em Postgres real (service no CI) — #130
- Vínculos Wazuh → cliente cadastrados em 03/11 (9 grupos: `RZK-*` → `rzk`, `TARGET-*` → `target`, `TESTES-HARDENING` → `ness`) — [roteiro](infra/docs/runbooks/wazuh.md)
- T06 onda 1 (03/11): 5 ativos criados no GLPI (Computers 111–114, NetworkEquipment 157) — [evidência](docs/execution/evidence/glpi-t06-assets-2026-11-03.md); 498 vínculos de ticket criados nos mesmos 5 ativos (OK do Ricardo, readback ok, rollback pela lista de ids); 10997 → NetworkEquipment 158 (Nova Energia, entidade 9) com 11 vínculos. Pendente: modelo um-ativo-por-aparelho vs. por-link (158 duplica o 131). Seriais dos 2 Fortigates (157, 158) já gravados no GLPI
- 2.5 T05 GLPI: Computers 108–110 (entidade 1) criados e 1419 vínculos de ticket reparados (874 / 560 / 30), readback igual ao Hub, segunda aplicação 0; duas exceções `callAsSystem` aprovadas pelo Ricardo, só neste lote — [evidência](docs/execution/evidence/glpi-t05-assets-2026-11-02.md)
- 2.3b Isolamento Hub ↔ GLPI aplicado em 03/11 (#140): senhas do banco fora do `.env` do Hub (`/etc/ness-os/glpi-{db,app}.env`), `glpi-db` em rede interna própria, senhas rotacionadas; Hub sem a variável e sem resolver `glpi-db`. [Evidência](docs/execution/evidence/glpi-hub-isolation-2026-11-03.md)
- P0 Fundação SOC (03/11): atendimento por função própria, `pendente_de_cliente`, validação com campo/valor/sinal no log, prazo de 45 s no modelo, frequência persistida por tenant+cluster (`freq_key`). Em produção na release `56c4659` (04/11, `promotion=PASS`), coluna `freq_key` criada
- Backfill Zabbix → Hub aplicado em 04/11: 29.151 incidentes recuperados gravados, `status` intacto — [evidência](docs/execution/evidence/zabbix-hub-recovery-2026-11-03.md)
- P1 contrato de sinais v1 validado por consumidor independente (#160): `tenant_id` rejeitado na entrada, `severity_source.value` opcional, idempotência sem `tenant_id`
- P2 camada 1, primeiro corte só backend (#161): fila por prioridade, filtros, `ticket_state`, `/timeline`, `X-Request-ID`; Hub envia urgência/impacto ao GLPI (#158); prazos de resposta aceitos (#159)
- T08 diagnóstico do atendimento no GLPI (#156) e T07 preparo dos agentes: script com dry-run e rota `/Inventory` de exemplo (#157), nada aplicado em produção
- Recuperação Zabbix → Hub ligada em 03/11 (ação 7 e media type 72): antes nenhum incidente era marcado como recuperado. Frontend com o contador novo promovido em 04/11 (#149) — [evidência](docs/execution/evidence/zabbix-hub-recovery-2026-11-03.md)

### Em andamento
- P3 backend (PR `feat/p3-notificacoes`): e-mail + Web Push com registro, ack e escalonamento; aviso só a partir da severidade Zabbix 4 (decisão de 05/11, `_MIN_SEVERITY`; sev 3 tem ~1.731 abertos); falta UI/PWA, confirmar mapa severidade→janela e a escala de plantão
- Zabbix sem vínculo em `n_infraops_tenant_mappings`: fica `pendente_de_modalidade` até o Ricardo decidir o mapeamento cliente ↔ Zabbix

- Identidade: ADR 0015 (Entra ID único IdP, Authentik sai). Execução só após o aceite do MVP e o gate da Fase 0; UAT da Fase 1 segue sobre o Authentik atual. Não mexer em Authentik, Entra, DNS, firewall, Caddy nem Cloudflare até lá. Preparável em branch, sem deploy: Fase A (autorização local no Hub, vínculo por issuer + oid). Desenho: [identity-access-perimeter](docs/superpowers/specs/2026-11-05-identity-access-perimeter-design.md)

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
