# ADR 0014 — Entrega integrada e escalonada do ness.OS

- Status: aceita
- Data: 22/08/2026
- Decisor: Ricardo Esper

## Contexto

A arquitetura oficial descreve o teto de 5.000 endpoints, mas o projeto não precisa contratar essa capacidade no primeiro dia. Infraestrutura, sistemas canônicos, AIOps, portal e operação também precisam formar uma cadeia única de entrega, sem fontes concorrentes de status.

## Decisão

Executar o ness.OS pelo projeto diretor `docs/ecosystem-completion-plan.md`, com 13 pacotes de trabalho e oito marcos de aceite. GitHub controla código e configuração; GLPI controla execução gerencial; ness.OS consolida indicadores e evidências.

A primeira operação integrada possui horizonte de planejamento de 18 semanas. O Wazuh Onda 1, com oito VPS, somente será liberado após o Gate 6 do núcleo. A expansão para 10 e 11 VPS ocorrerá apenas pelos gatilhos de capacidade aprovados, até o teto de 5.000 endpoints.

A API Contabo começa read-only. Mutações de infraestrutura permanecem fora do MVP e exigirão mudança, dupla confirmação, auditoria e `platform_admin`.

## Consequências

- Recuperação, identidade, Zabbix, GLPI e núcleo AIOps precedem a expansão Wazuh.
- Capacidade não utilizada não será comprada antecipadamente.
- Cada release termina com evidência e critério de saída.
- Atraso em um pacote dependente não autoriza pular controles ou simular indicadores.
- O cronograma é revisto por capacidade real e disponibilidade de responsáveis, sem alterar os gates de segurança.
