# ness.OS

**Tipo:** app

**Estágio:** em andamento

**Próximo passo:** conferir a promoção da API do Hub (26/10 23:10); com OK do Ricardo, criar o bucket `ness-os-tfstate` e aplicar o import do Terraform (1.1).

## Quadro (atualizado a cada task fechada)

Tasks do [plano de execução](docs/superpowers/plans/2026-10-26-ness-os-execution-plan.md).

### Feito
- 0.1 Reconciliar estado — [evidência](docs/execution/evidence/state-reconciliation-2026-10-26.md)
- 0.3 CI — Actions religado; #81, #64 e #85 na `main`
- 0.4 Ferramental IaC (`infra/bin/tf`, `infra/bin/ansible`) — #89
- 1.1 Terraform importa as 3 VPS + Object Storage, `prevent_destroy`, guard de plano — #92 (plano limpo; falta backend e `apply`)
- 1.2 Role `common`: drop-in `zz-`, validação com rollback, hostname real — #94 (falta `--check` nos hosts)
- 2.1 Matriz negativa GLPI T03 em lab, correção do gateway — #91
- 2.4 GLPI T04: um ticket por alerta; 403 libera a reserva — #93
- 6.1 + 6.3 Testes do frontend (vitest) e isolamento do SSE — #90
- Imagens do Hub publicadas da `main` `8cf3925`, pacotes públicos

### Em andamento
| Task | Onde | Situação |
|---|---|---|
| 3.1 Promoção API + workers | timer `ness-hub-promote-8cf3925`, 26/10 23:10; script no PR #86 | rollback automático |

### Pronto para começar
- 1.3 As-built gerado (leitura nos 3 hosts)
- 1.2 Step 5: `--check --diff` da role nos 3 hosts (só leitura)
- 2.2 ADR 0020 aceito com o resultado do lab
- 6.2 + 6.4 Verdade operacional e matriz de entidades
- 8.1 Contrato e sanitização da IA
- 0.2 Limpeza da raiz (revisão do Ricardo no fim)

### Esperando o Ricardo
1. OK para criar o bucket `ness-os-tfstate` (privado, versionado) e GO do `apply` do import (1.1)
2. 9.1 BOM Wazuh (#88): volumetria real do Wazuh Hostinger (SSH leitura, usuário leitura ou 3 comandos)
3. Issue #82: segredos antigos em refs do GitHub, agora com repositório público
4. Restringir a chave do agente à `stack` (`from=`)
5. Fechar o PR #84 (CI local, substituído pelo Actions)
6. Depois: D2 janela GLPI, D4 MFA, D3/D6 compras Psono/Wazuh

## Foco

- Escopo e decisões de produto: `docs/superpowers/plans/2026-10-12-ness-os-plano-master.md`.
- Estado factual: `docs/execution/ness-os-status.md`.
- Implantação em VPS nova depende de contratação aprovada pelo Ricardo; todo recurso nasce em `infra/terraform` e `infra/ansible`.
