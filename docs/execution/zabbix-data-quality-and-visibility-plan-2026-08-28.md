# Plano Zabbix — qualidade de coleta e visibilidade

Data: 2026-08-28 (BRT)  
Estado: aprovado para execução por ondas após a restauração isolada mais recente.  
Escopo: Zabbix; não ativa ações, mídias, conectores ou coleta produtiva sem
gate explícito.

## Objetivo

Transformar o Zabbix de uma fonte de alertas heterogêneos em uma fonte
confiável de saúde de serviços, ativos e conectividade para operação ness.OS e
visões somente-leitura de cada cliente. A ordem é deliberada:

```text
dados corretos -> alertas qualificados -> serviços -> painéis/mapas -> marca ness.
```

Dashboards não compensam coleta incorreta. Nenhum número executivo será
classificado como confiável antes de passar pelos gates de qualidade abaixo.

## Fotografia que guia a priorização

Leitura da origem em 2026-08-27, sem alteração:

| Indicador | Situação |
| --- | ---: |
| Hosts cadastrados / habilitados | 614 / 252 |
| Itens ativos | 42.333 |
| Itens não suportados ativos | 1.801 |
| Hosts habilitados sem template | 14 |
| Agente: OK / desconhecido / indisponível | 90 / 87 / 23 |
| SNMP: OK / desconhecido / indisponível | 59 / 19 / 9 |
| Problemas abertos | 3.068 |

As baselines restauradas anteriores têm números diferentes porque refletem
datas e conjuntos distintos. Após o restore mais recente, será gerado um único
relatório de referência. Ele substitui esta fotografia para fins de aceite, sem
apagar as evidências históricas.

### Focos conhecidos

1. FortiGate e links: mais de 1.142 itens não suportados; hosts de links
   receberam coleta integral de appliance e podem duplicar métricas.
2. VMware, storage e Windows: itens incompatíveis, em especial WMI e
   `perf_counter`; tratar causa, não silenciar em massa.
3. Cobertura: hosts sem template, sem tags e disponibilidade indefinida de
   agente/SNMP.
4. Ruído: severidade e dependências inadequadas antes de qualquer escalonamento.

## Princípios operacionais

- A origem atual permanece rollback durante a migração; não é laboratório.
- Alterações de host/template ocorrem por API ou interface, nunca por SQL.
- Cada onda exporta o estado anterior e usa **Unlink**, nunca **Unlink and
  clear**; histórico e rollback são preservados.
- Piloto limitado a Cavan — Matriz e a no máximo 25 hosts por mudança.
- GLPI é a referência para cliente, localidade, responsável, criticidade e
  endereço; o agente GLPI coleta inventário técnico, mas não substitui esse
  cadastro de serviço.
- Nenhuma credencial de SNMP, VMware ou agente entra em documentação ou Git;
  antes da produção ficará sob o cofre escolhido.

## Ondas de execução

| Onda | Resultado | Ações | Aceite / rollback |
| --- | --- | --- | --- |
| 0 — baseline | Medida única pós-restore | Inventariar hosts, templates, `unsupported`, queue, NVPS, busy, disponibilidade, problemas e mapas. Exportar objetos do piloto. | Relatório assinado; nenhuma coleta/alerta habilitado. |
| 1 — rede/FortiGate | Um appliance por firewall, interfaces por descoberta | Corrigir 58 hosts de links herdados; piloto com dois links; remover apenas item de disco se o equipamento não o expõe. | Paridade de link 24–72 h; host legado apenas desabilitado por 30 dias. |
| 2 — switches, VMware e storage | Template adequado ao ativo real | Substituir o uso indevido de `FortiGate by HTTP` em switches; validar URL, macros e versão VMware; corrigir storage por fabricante/modelo. | Export/relink restaura o estado anterior. |
| 3 — Windows e Linux | Agente utilizável e métricas compatíveis | Separar falha de agente de chave WMI/perf-counter; atualizar template somente após provar versão e permissões. | Reduzir `unsupported` sem reduzir cobertura de disponibilidade. |
| 4 — modelo operacional | Ativos pesquisáveis e serviços mensuráveis | Aplicar tags `tenant`, `site`, `service`, `environment`, `technology`, `scope`, `owner`, `role`, `criticality`; quarentenar grupos vazios. | Amostra do piloto 100% etiquetada; grupos não são excluídos. |
| 5 — alertas | Eventos acionáveis, não ruído | Dependências, janelas, severidades, correlação dos dois links Cavan e monitoração do próprio Zabbix. Testar canal sintético antes de canais reais. | Redução de eventos repetidos; ação real continua desabilitada até aceite. |
| 6 — visibilidade | Painéis e mapas baseados em dados aprovados | Construir dashboards e mapas abaixo; publicar somente recortes autorizados por tenant. | Números reconciliam com Zabbix; teste desktop e celular. |
| 7 — identidade visual | Experiência ness. sem bloquear upgrade | Aplicar camada reversível de logo, favicon, CSS e textos no frontend, sem editar core do Zabbix. | Backup, teste de upgrade e reversão comprovados. |

## Painéis e mapas a entregar

| Público | Painel | Indicadores iniciais |
| --- | --- | --- |
| NOC/SOC ness. | Operação geral | disponibilidade, problemas qualificados, filas, NVPS, busy, proxies, backup e saúde do Zabbix |
| Sustentação | Qualidade de coleta | `unsupported`, `unknown`, hosts sem template/tag, disponibilidade de agente/SNMP e idade da última coleta |
| Governança | Serviços e SLO | saúde por serviço, disponibilidade, tendências, capacidade e riscos; sem alertas brutos |
| Cliente | Saúde do tenant | serviços, sites, conectividade, manutenção e incidentes qualificados do próprio tenant |
| Engenharia | Capacidade e plataforma | MariaDB, frontend, server, proxies, I/O, histórico e tendência de crescimento |

Mapas serão separados por tenant e por objetivo: infraestrutura/conectividade e
serviços de negócio. Para Cavan — Matriz, os mapas UAT existentes são a base;
coordenadas, endereços e criticidade devem ser reconciliados no GLPI antes de
ampliar a geolocalização.

## Metas de qualidade

As metas são progressivas, medidas sobre a baseline pós-restore, não uma
exigência artificial de zerar tudo no primeiro corte:

| Marco | Medida de sucesso |
| --- | --- |
| Piloto | 100% dos hosts do piloto com template, tags e owner; nenhum item sintético criado para mascarar lacuna de fabricante. |
| Onda rede | redução mínima de 70% dos `unsupported` ligados a FortiGate sem duplicar coleta. |
| Onda sistemas | todo `unsupported` restante classificado como incompatibilidade, credencial, conectividade ou exceção aceita. |
| Antes do painel executivo | disponibilidade e severidade revisadas no recorte publicado; problemas históricos identificados como históricos. |
| Pós-corte | D+1, D+3 e D+7 com queue/NVPS/busy, backup e tendências sem regressão. |

## Riscos e controles

- **Template errado:** testar um ativo representativo e observar antes do lote.
- **Credenciais ausentes:** registrar como bloqueio; nunca criar dado fictício.
- **Dupla coleta:** manter host legado somente para comparação e desligá-lo após
  aceite, sem exclusão imediata.
- **Alerta em massa:** ações e mídias permanecem desabilitadas até o teste
  sintético e aceite da política.
- **Exposição entre clientes:** tags, grupos e permissões devem ser testados
  com perfil cliente somente-leitura antes de publicar painel externo.

## Próximo passo operacional

Concluir a transferência com SHA-256, restaurar no ambiente isolado e gerar a
baseline da Onda 0. Em seguida, executar **somente a Onda 1 no piloto Cavan —
Matriz**. Dashboards executivos, mapas finais e a customização ness. começam
depois que esse piloto tiver dados confiáveis.

## Referências

- [Baseline UAT de polimento](zabbix-uat-polishment-baseline-2026-08-26.md)
- [Onda A — FortiGate](zabbix-wave-a-fortigate-plan-2026-08-24.md)
- [Checklist de transmutação e corte](zabbix-post-restore-transmutation-cutover-checklist.md)
- [Brand baseline ness.](../brand/ness-brand-baseline.md)
