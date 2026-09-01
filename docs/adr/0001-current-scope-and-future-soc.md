# ADR 0001 — Escopo atual e segunda etapa SOC

- Status: aceita
- Data: 20/08/2026
- Decisor: Ricardo Esper

## Contexto

O repositório contém infraestrutura e planos para Wazuh Hub/Spokes e MISP, mas o ambiente atual confirmado possui duas VPS: Zabbix/NOC e Hub AIOps. A expansão SOC exige novas máquinas.

## Decisão

Concluir, regularizar e estabilizar primeiro as duas VPS atuais. Wazuh e MISP ficam para uma segunda etapa, com arquitetura, capacidade e orçamento próprios.

## Consequências

- Novas funções SOC não bloqueiam a estabilização do núcleo.
- Terraform e documentação devem separar recursos atuais de recursos futuros.
- A segunda etapa só inicia após o Gate 4 do plano diretor e aprovação de máquinas adicionais.
