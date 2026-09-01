# Contrato inicial de indicadores executivos — ness.OS

> Estado: baseline para implementação; fórmulas e metas precisam de homologação pelos owners de domínio.

## Regra de confiança

Um indicador só pode aparecer como real quando possuir estes campos:

| Campo | Obrigatório |
|---|---|
| `id`, nome e descrição de negócio | sim |
| tenant/escopo e permissões | sim |
| sistema fonte e consulta/versionamento | sim |
| fórmula, unidade e janela temporal | sim |
| meta, faixas e direção desejada | sim |
| timestamp da observação e da coleta | sim |
| estado `ok`, `stale`, `partial`, `unavailable` ou `provisional` | sim |
| cobertura/qualidade e motivo de degradação | sim |
| owner e drill-down para a evidência | sim |

Zero é um valor válido, não um fallback. Falha de coleta deve resultar em `unavailable`; atraso acima do SLA de atualização deve resultar em `stale`.

## Modelo mínimo de resposta

```json
{
  "id": "support.sla_compliance",
  "label": "Cumprimento de SLA",
  "value": null,
  "unit": "percent",
  "status": "unavailable",
  "scope": { "tenant_id": "tenant-uuid", "period": "P30D" },
  "source": { "system": "glpi", "dataset": "tickets" },
  "observed_at": null,
  "collected_at": "2026-08-21T14:00:00Z",
  "quality": { "coverage_percent": 0, "reason": "SLA ainda não homologado" },
  "target": { "operator": ">=", "value": 95 },
  "owner": "governanca",
  "drilldown_url": null
}
```

## Catálogo executivo inicial

| Domínio | Indicador inicial | Fonte canônica pretendida | Situação inicial |
|---|---|---|---|
| Visão geral | saúde de serviços críticos | GLPI + Zabbix + incidentes | fórmula a homologar; não publicar score arbitrário |
| Visão geral | incidentes críticos abertos e tendência | Hub/GLPI | separar incidente de alerta |
| Visão geral | cumprimento global de SLA | GLPI | depende do catálogo e regras de SLA |
| Projetos | projetos on-track/em risco/atrasados | Projetos GLPI Community, em homologação | direção provisória; nenhuma simulação permitida |
| Projetos | marcos vencidos e próximos 30 dias | Projetos/tarefas GLPI Community | depende da taxonomia e do piloto |
| Governança | serviços com owner, criticidade e SLA | GLPI | iniciar com catálogo de 10–20 serviços |
| Governança | riscos/controles vencidos | GRC/fonte a decidir | contrato necessário |
| Infraestrutura | disponibilidade de serviços críticos | Zabbix associado ao serviço GLPI | depende do vínculo serviço–ativo |
| Infraestrutura | cobertura e atualidade do monitoramento | Zabbix + GLPI | iniciar na baseline dos 7.000 ativos |
| Infraestrutura | sucesso e restauração de backups | jobs de backup + evidências | coletar sucesso, idade e último restore |
| Sustentação | backlog, idade, MTTA e MTTR | GLPI | exige taxonomia e timestamps homologados |
| Sustentação | reabertura e cumprimento de SLA/OLA | GLPI | depende do desenho de processo |
| Segurança | incidentes por severidade, MTTD e MTTR | Hub/Wazuh | entra com o piloto Wazuh; não contar alertas como incidentes |
| Segurança | cobertura de agentes e vulnerabilidades críticas vencidas | Wazuh + GLPI | entra na segunda etapa |
| Qualidade de dados | cobertura, duplicidade, atualidade e fontes degradadas | ness.OS + fontes | obrigatório em todas as telas executivas |

## Cortes por audiência

- **Stakeholder/executivo:** saúde, tendência, impacto, risco, SLA, projetos e decisões necessárias.
- **Cliente:** somente seu tenant, serviços contratados, SLA, incidentes, mudanças e projetos autorizados.
- **Governança:** catálogo, ownership, contratos, riscos, controles e qualidade cadastral.
- **Infraestrutura:** ativos, disponibilidade, capacidade, backup e mudança.
- **Sustentação:** filas, backlog, incidentes/problemas, MTTA/MTTR e SLA/OLA.
- **Segurança:** cobertura, exposição, incidentes e resposta.

## Sequência de implementação

1. Remover ou marcar todos os números demonstrativos do protótipo atual.
2. Criar inventário de indicadores existentes com fonte e fórmula.
3. Entregar envelope comum de proveniência/qualidade na API.
4. Integrar primeiro GLPI e Zabbix por serviço/tenant; não deduplicar apenas por soma.
5. Publicar a primeira visão executiva com indicadores reais e estados de ausência explícitos.
6. Acrescentar Projetos após homologar o módulo nativo do GLPI; acrescentar GRC após decidir sua fonte canônica.
7. Validar o painel com uma persona de cada público e registrar aceite.

## Critério de aceite da primeira versão

- nenhum número demonstrativo aparece como real;
- todos os cards mostram período, atualização, qualidade e fonte;
- filtros de tenant e permissões passam em testes negativos;
- cada indicador possui drill-down até sua evidência;
- fontes indisponíveis degradam individualmente sem zerar o dado;
- ao menos um indicador real e homologado de Governança, Infraestrutura e Sustentação está disponível;
- projetos e Segurança aparecem como `unavailable/not_configured` até suas fontes serem aprovadas;
- painel responsivo e utilizável na PWA para as jornadas autorizadas.
