# ness.OS

**Tipo:** app

**Estágio:** em andamento

**Próximo passo:** Task 2.3 (gateway T03 em produção) e 2.5 (T05) em laboratório.

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
- 2.4 GLPI T04: um ticket por alerta; 403 libera a reserva — #93
- 3.1 Hub API + workers em `412bdc0` desde 27/10 — [evidência](docs/execution/evidence/hub-release-2026-10-26.md); promoção de 26/10 revertida (regressão GLPI, corrigida no #95); canário de alertas no script — #86
- 6.1 + 6.3 Testes do frontend (vitest) e isolamento do SSE — #90
- 6.2 Frescor/último sucesso/erro por fonte em `pipeline_health`, `ready` e exit code do monitor; UI sem hora falsa — #101
- Reconciliação dos alertas de 26–27/10: 739 sem ticket, 215 sem cobertura — #102
- 8.1 Contrato `AIRequestV1`, sanitização e métrica das chamadas ao Gemini — #99 (corrigiu vazamento de segredo para o Gemini em análise e triagem SOC)

### Em andamento
_nenhuma_

### Pronto para começar
- 2.5 T05 do plano GLPI

### Esperando o Ricardo
1. Replay dos 14 alertas ainda ativos sem ticket (Google Updater parado e disco em `alpdb01`/`alpdb02`)? Os 12 FortiGate já ganharam ticket; os 189 resolvidos ficam sem
2. 9.1 BOM Wazuh (#88): acesso SSH de leitura ao Wazuh Hostinger (`62.72.8.164`; porta 22 não responde da `stack`)
3. Issue #82: rotacionar senhas admin/SSO do GLPI, root MariaDB e chave S3 de backup (sem reescrever histórico)
4. Restringir a chave do agente à `stack` (`from=`)
7. Depois: D4 MFA, D3/D6 compras Psono/Wazuh

## Foco

- Escopo e decisões de produto: `docs/superpowers/plans/2026-10-12-ness-os-plano-master.md`.
- Estado factual: `docs/execution/ness-os-status.md`.
- Implantação em VPS nova depende de contratação aprovada pelo Ricardo; todo recurso nasce em `infra/terraform` e `infra/ansible`.
