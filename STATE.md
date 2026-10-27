# ness.OS

**Tipo:** app

**Estágio:** em andamento

**Próximo passo:** 6.2 + 6.4 e 0.2 em paralelo; com OK do Ricardo, criar o bucket `ness-os-tfstate` e aplicar o import do Terraform (1.1).

## Quadro (atualizado a cada task fechada)

Tasks do [plano de execução](docs/superpowers/plans/2026-10-26-ness-os-execution-plan.md).

### Feito
- 0.1 Reconciliar estado — [evidência](docs/execution/evidence/state-reconciliation-2026-10-26.md)
- 0.3 CI — Actions religado; #81, #64 e #85 na `main`
- 0.4 Ferramental IaC (`infra/bin/tf`, `infra/bin/ansible`) — #89
- 1.1 Terraform importa as 3 VPS + Object Storage, `prevent_destroy`, guard de plano — #92 (plano limpo; falta backend e `apply`)
- 1.2 Role `common` — #94; `--check` nos 3 hosts — #97 ([evidência](docs/execution/evidence/ansible-common-check-2026-10-27.md); `apply` bloqueado por UFW/chave/sudoers)
- 1.3 As-built gerado dos 3 hosts — #98
- 2.1 Matriz negativa GLPI T03 em lab, correção do gateway — #91
- 2.2 Step 1: ADR 0020 com contrato e resultado do lab, status proposta — #96
- 2.4 GLPI T04: um ticket por alerta; 403 libera a reserva — #93
- 3.1 Hub API + workers em `412bdc0` desde 27/10 — [evidência](docs/execution/evidence/hub-release-2026-10-26.md); promoção de 26/10 revertida (regressão GLPI, corrigida no #95); canário de alertas no script — #86
- 6.1 + 6.3 Testes do frontend (vitest) e isolamento do SSE — #90
- 8.1 Contrato `AIRequestV1`, sanitização e métrica das chamadas ao Gemini — #99 (corrigiu vazamento de segredo para o Gemini em análise e triagem SOC)

### Em andamento
_nenhuma_

### Pronto para começar
- 6.2 + 6.4 Verdade operacional e matriz de entidades
- 0.2 Limpeza da raiz (revisão do Ricardo no fim)
- 1.2 ajustes para `apply`: UFW por host, chave antiga, sudoers existente
- Reconciliar alertas que falharam em 26–27/10 (`glpi_backlog_classify.py`, leitura)

### Esperando o Ricardo
1. OK para criar o bucket `ness-os-tfstate` (privado, versionado) e GO do `apply` do import (1.1)
2. 9.1 BOM Wazuh (#88): volumetria real do Wazuh Hostinger (SSH leitura, usuário leitura ou 3 comandos)
3. Issue #82: segredos antigos em refs do GitHub, agora com repositório público
4. Restringir a chave do agente à `stack` (`from=`)
5. Fechar o PR #84 (CI local, substituído pelo Actions)
6. Aprovar o ADR 0020 (2.2 Step 2) junto da janela D2 GLPI
7. Depois: D4 MFA, D3/D6 compras Psono/Wazuh

## Foco

- Escopo e decisões de produto: `docs/superpowers/plans/2026-10-12-ness-os-plano-master.md`.
- Estado factual: `docs/execution/ness-os-status.md`.
- Implantação em VPS nova depende de contratação aprovada pelo Ricardo; todo recurso nasce em `infra/terraform` e `infra/ansible`.
