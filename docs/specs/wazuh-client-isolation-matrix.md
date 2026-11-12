# Wazuh — isolamento por cliente

Decidido com o Ricardo em 12/11/2026. Base: 624 agentes, ~893 mil alertas/dia, ~1 GB/dia de índice.

## Níveis

| Nível | Modelo | Quando |
|---|---|---|
| **A** | Spoke compartilhado, até 3 clientes por spoke; DLS/RBAC no indexer; fail-closed via `n_infraops_tenant_mappings` | Padrão |
| **B** | Spoke dedicado ao cliente | Cliente grande, regulado ou com exigência de segregação |
| **C** | Stack dedicada (manager + indexer + dashboard) | Só com cláusula contratual |

## Matriz

| Nível | Clientes |
|---|---|
| B | alupar, alupar-pe, alupar-co, target, unimed |
| A | tbe, ltb, bichara, cavan, nova-energia, numen, tne, ness |
| pendente | rzk |

## Gatilhos para subir de nível

Qualquer um, por spoke: >300 agentes; >5 GB/dia de índice; `events_dropped` recorrente; CPU p95 >60% por 14 dias.

## Infra

- Sem VPS nova agora. Base: o Zabbix antigo (`ninfraops-zabbix`, 203409070). Decisão do Ricardo em 12/11: a janela de rollback do cutover é de 48 h (D+2, gate em [zabbix-cutover-janela.md](../runbooks/zabbix-cutover-janela.md)); passado o gate, a máquina é recriada para o Wazuh.
- Hostinger (62.72.8.164) é origem temporária. Só desativar depois dos critérios de [ecosystem-completion-plan.md](../ecosystem-completion-plan.md) (Onda 2): borda redundante, teste N−1 aprovado, ≥98% dos agentes comunicando e 7–14 dias de estabilidade.
- Contratos por cliente (Brain/CMS) podem mover alguém para B ou C.
