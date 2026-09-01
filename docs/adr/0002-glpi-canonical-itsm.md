# ADR 0002 — GLPI como ITSM e inventário/CMDB canônicos

- Status: aceita
- Data: 20/08/2026
- Decisor: Ricardo Esper

## Contexto

GLPI já está instalado no Hub AIOps, enquanto o backend ainda contém referências e integração com DeskManager. A base terá aproximadamente 7.000 ativos e precisa de uma fonte mestra independente da troca futura de RMM.

## Decisão

GLPI será o único ITSM canônico e a fonte mestra de inventário/CMDB. O GLPI Agent fará a coleta de inventário dos endpoints. DeskManager será removido após inventário de dependências e confirmação de que não há obrigação contratual ou dados a migrar.

## Consequências

- Categorias, entidades, SLAs, usuários e correlação de incidentes serão modelados no GLPI.
- A implantação do GLPI Agent ocorrerá por ondas, com piloto, regra de identidade/deduplicação e indicadores de cobertura, atualização e falha.
- Dados de SuperOps, Atera, Datto e Zabbix serão reconciliados com o ativo canônico no GLPI; não constituirão cadastros mestres paralelos.
- O GLPI Agent será distribuído pelo RMM já presente em cada ativo durante a transição.
- O fluxo ponta a ponta terá um único `ticket_id`.
- Código, variáveis, workflows e documentação de DeskManager tornam-se dívida de remoção.
