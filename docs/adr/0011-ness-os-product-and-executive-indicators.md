# ADR 0011 — ness.OS como camada unificada e indicadores executivos permanentes

- Estado: aceito
- Data: 21/08/2026
- Decisor: Ricardo Esper

## Contexto

O produto vinha sendo descrito principalmente como Hub AIOps/NOC/SOC. Essa descrição é insuficiente. A visão aprovada é disponibilizar a stakeholders, clientes e equipes internas uma visão contextual da saúde da TI, do portfólio de projetos e dos domínios de Governança, Infraestrutura, Sustentação e Segurança.

O frontend atual já possui um protótipo executivo, porém parte dos valores é demonstrativa e o score global usa uma fórmula provisória baseada em contagem de alertas. Números sem fonte, escopo, fórmula, atualização e qualidade conhecidas não podem ser apresentados como indicadores gerenciais.

## Decisão

1. O **ness.OS é a camada unificada de experiência, contexto e inteligência da TI**, não um substituto monolítico das ferramentas especializadas.
2. Os sistemas canônicos continuam responsáveis pelos fatos: GLPI por serviços, inventário e ITSM; Zabbix por monitoramento; Wazuh por segurança quando implantado; e a futura ferramenta de portfólio pelo status de projetos.
3. O modelo comum do produto relacionará `tenant`, `serviço`, `ativo`, `projeto`, `risco`, `controle`, `incidente`, `SLA` e `responsável`.
4. Coleta e qualidade dos indicadores, assim como a evolução do painel executivo, serão objetivos permanentes em todas as fases e Gates.
5. Todo indicador exibido terá definição versionada, owner, fonte, fórmula, escopo/tenant, unidade, meta, periodicidade, timestamp, qualidade e caminho de drill-down.
6. Valor ausente, atrasado, parcial ou degradado será mostrado como tal. É proibido substituir ausência por zero, somar entidades não deduplicadas ou apresentar dados demonstrativos como reais.
7. Alertas permanecem nas plataformas de origem. O histórico corporativo do ness.OS guardará incidentes qualificados e agregados necessários aos indicadores, conforme a política de retenção.
8. O acesso será orientado por persona e tenant: executivo/stakeholder, cliente, Governança, Infraestrutura, Sustentação e Segurança.

## Consequências

- O painel executivo deixa de ser entrega tardia da Fase 5 e passa a evoluir desde a baseline.
- O score global somente será publicado depois de fórmula, pesos, qualidade mínima e owner aprovados; até lá, será marcado como indisponível/provisório.
- Métricas de projetos não serão inventadas nem mantidas manualmente no Hub como fonte paralela; a origem canônica ainda precisa ser decidida.
- APIs e componentes deverão expor proveniência, atualização e qualidade junto ao valor.
- O contrato inicial está em [`../specs/executive-indicators-contract.md`](../specs/executive-indicators-contract.md).
