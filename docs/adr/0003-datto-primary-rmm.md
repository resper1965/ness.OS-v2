# ADR 0003 — SuperOps como candidato RMM-alvo

- Status: provisória
- Data: 20/08/2026
- Decisor: Ricardo Esper

## Contexto

O ecossistema possui ativos atendidos por Datto e Atera, mas precisa de uma solução-alvo. SuperOps foi indicado como candidato. O inventário/CMDB canônico ficará no GLPI, e a implantação do GLPI Agent precisa alcançar ativos durante a transição entre RMMs.

## Decisão

SuperOps será o candidato RMM-alvo. A promoção para canônico depende de homologação de requisitos, APIs, segurança, licenciamento e migração. Datto e Atera continuarão suportados enquanto houver ativos dependentes. Em cada ativo, o RMM já instalado — SuperOps, Atera ou Datto — distribuirá e atualizará o GLPI Agent.

## Consequências

- Não ampliar automações exclusivas antes da homologação do SuperOps.
- Atera e Datto não podem ser removidos até existir inventário dos ativos dependentes.
- O RMM distribui o agente, mas não substitui o GLPI como cadastro mestre.
- A factory de RMM permanece e cada tenant/ativo deve ter provedor explícito; fallback automático é proibido.
