# ADR 0008 — Capacidade, SLO e manutenção

- Status: aceita
- Data: 20/08/2026
- Decisor: Ricardo Esper

## Contexto

A meta é suportar 7.000 ativos/endpoints e cinco operadores simultâneos. O histórico de alertas está em uma plataforma fechada sem exportação utilizável. Apenas o Zabbix está em produção.

## Decisão

- Capacidade-alvo: 7.000 ativos e cinco operadores.
- SLO mensal: 99,5% para portal/API e 99,9% para ingestão Zabbix.
- RPO/RTO permanecem 24 horas/4 horas.
- Mudanças que possam afetar Zabbix, proxies, banco, ingestão ou disponibilidade do monitoramento ocorrerão das 22:00 às 00:00 em `America/Sao_Paulo`, em qualquer dia, sempre agendadas.
- A janela poderá ser dispensada para ativos sem vínculo direto com a operação Zabbix, desde que a mudança tenha responsável, registro, avaliação de impacto, validação e rollback proporcionais ao risco.
- Antes do teste de carga, serão coletados 30 dias próprios de volume médio, pico e severidade no Zabbix/Hub.
- Alertas brutos terão retenção inicial máxima de 90 dias; incidentes confirmados, 12 meses. Métricas agregadas poderão permanecer sem payload sensível.

## Consequências

- O teste de carga deve reproduzir a distribuição real, não um número arbitrário de requests.
- A falta de exportação histórica não será compensada por estimativas apresentadas como fatos.
- Erro budget e janelas planejadas precisam ser registrados.
- A dispensa da janela não elimina o processo de gestão de mudanças nem autoriza indisponibilidade não avaliada em outros serviços.
- AIOps pode ser reorganizado em pré-produção; Zabbix exige backup e rollback antes de cada mudança.
