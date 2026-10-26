# ness.OS

**Tipo:** app

**Estágio:** em andamento

**Próximo passo:** conferir a promoção da API do Hub (26/10 23:10) e revisar os PRs das tasks 0.4, 2.1, 6.1+6.3 e 9.1.

## Quadro (atualizado a cada task fechada)

Tasks do [plano de execução](docs/superpowers/plans/2026-10-26-ness-os-execution-plan.md).

### Feito
- 0.1 Reconciliar estado — [evidência](docs/execution/evidence/state-reconciliation-2026-10-26.md)
- 0.3 CI — Actions religado; #81, #64 e #85 na `main`
- Imagens do Hub publicadas da `main` `8cf3925` (API `26b6b6d9…`, frontend `ceb0e533…`), pacotes públicos

### Em andamento
| Task | Branch / PR | Executor |
|---|---|---|
| 3.1 Promoção API + workers | timer `ness-hub-promote-8cf3925`, 26/10 23:10; script no PR #86 | AIOps, rollback automático |
| 0.4 Ferramental IaC | `chore/iac-tooling` | subagente (Sonnet) |
| 2.1 Matriz negativa GLPI T03 (lab) | `test/glpi-t03-matrix` | subagente (Sonnet) |
| 6.1 + 6.3 Testes frontend e SSE | `test/hub-frontend-sse` | subagente (Sonnet) |
| 9.1 BOM Wazuh | `docs/wazuh-bom` | subagente (GLM) |

### Pronto para começar
- 1.1 → 1.2 → 1.3 Terraform/Ansible/as-built (após 0.4)
- 2.4 Ticket único (T04, testes)
- 6.2 + 6.4 Verdade operacional e matriz de entidades
- 8.1 Contrato e sanitização da IA
- 0.2 Limpeza da raiz (revisão do Ricardo no fim)

### Esperando o Ricardo
1. Issue #82: segredos antigos em refs do GitHub, agora com repositório público
2. Restringir a chave do agente à `stack` (`from=`)
3. Fechar o PR #84 (CI local, substituído pelo Actions)
4. Depois: D2 janela GLPI, D4 MFA, D3/D6 compras Psono/Wazuh

## Foco

- Escopo e decisões de produto: `docs/superpowers/plans/2026-10-12-ness-os-plano-master.md`.
- Estado factual: `docs/execution/ness-os-status.md`.
- Implantação em VPS nova depende de contratação aprovada pelo Ricardo; todo recurso nasce em `infra/terraform` e `infra/ansible`.
