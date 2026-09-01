# Diagnóstico — backlog de escalations do Zabbix

> Data: 20/08/2026
> Estado: diagnóstico concluído; correção funcional pendente de janela
> Escopo: VPS Zabbix/NOC

## Sintoma

- Carga observada próxima de `6` em 8 vCPU.
- MariaDB usando aproximadamente dois núcleos e três processos `escalator` usando cerca de 40% de CPU cada.
- Os escalators informavam milhares de registros processados em ciclos de 9–13 minutos.
- Zabbix, MariaDB e Apache permaneceram ativos, o frontend respondeu HTTP 200, nenhuma unidade estava em falha e não houve recorrência do minerador.

## Evidência de banco

- Aproximadamente 17.848 registros em `escalations`.
- Distribuição por ação:
  - ação 6, `Report unknown triggers`: 11.511;
  - ação 4, `Report not supported items`: 5.283;
  - ação 3, `Report problems to Zabbix administrators`: 567;
  - ação 5, `Report not supported low level discovery rules`: 70.
- 16.141 registros estavam com `nextcheck=0`; 744 registros não zero estavam vencidos no momento da leitura.
- As operações das ações 3–6 possuem apenas o passo 1. Não foi identificada repetição infinita de passos.
- Estado operacional atual:
  - 1.351 itens ativos não suportados;
  - 634 triggers ativos desconhecidos.

## Principais geradores de itens não suportados

| Host | Itens ativos não suportados |
|---|---:|
| Numen IT Matriz Fortigate 61F Link Vivo wan2 | 344 |
| NESS Matriz Fortigate 200E Link Mundivox wan2 | 127 |
| vmware01, vmware02, vmware03, vmware05, vmware135 e vmware146 | 46 cada |
| HPe Storage MSA | 33 |
| série ALPCOL* observada | 21 por host nos maiores casos |

## Interpretação

As ações internas notificam transições de itens para `unsupported`, triggers para `unknown` e regras LLD para estado não suportado. Elas não são a coleta em si. Os registros persistentes estão associados a eventos ainda abertos/aguardando recuperação; remover registros diretamente ou apenas aumentar `StartEscalators` trataria o sintoma e poderia perder a trilha de notificação.

O servidor já possui três escalators, acima do padrão documentado de um. Aumentar novamente, com MariaDB já consumindo CPU, não é a primeira ação recomendada.

## Plano para a janela 22:00–00:00

1. Confirmar conclusão e checksums do backup Zabbix das 22:00 antes de qualquer alteração funcional.
2. Exportar configuração das ações internas 3–6 e capturar contagens de fila/estado como evidência anterior.
3. Inspecionar os erros dos 344 itens do FortiGate Numen e dos 127 itens do FortiGate NESS; classificar em credencial, OID/template, interface, timeout ou item realmente inexistente.
4. Comparar os seis VMware com 46 falhas idênticas e corrigir o template/macros na origem uma única vez.
5. Corrigir ou desabilitar somente itens comprovadamente inválidos. Não desabilitar hosts nem templates completos em massa.
6. Restringir as ações internas a grupos/objetos operacionais relevantes e evitar notificações universais de estados conhecidos durante a remediação.
7. Preservar eventos e escalations; permitir que o Zabbix feche os registros por recuperação normal. Qualquer limpeza SQL exigirá backup, consulta upstream e aprovação separada.
8. Medir após cada lote: itens não suportados, triggers desconhecidos, escalations vencidas, CPU MariaDB e `zabbix[process,escalator,avg,busy]`.
9. Abortar se ingestão, frontend, banco ou proxies degradarem, ou se a fila crescer após a mudança.

## Critério de estabilização

- Nenhum host com centenas de itens não suportados sem justificativa.
- Escalations vencidas em tendência contínua de queda.
- Escalator médio abaixo de 75% busy por 15 minutos.
- Sem perda de ingestão, notificações de incidentes reais ou recuperação.
- Causa e correção documentadas por template/host.

## Referências

- [Zabbix 7.0 — notificações de itens não suportados](https://www.zabbix.com/documentation/7.0/en/manual/config/notifications/unsupported_item)
- [Zabbix 7.0 — itens internos e monitoramento de processos](https://www.zabbix.com/documentation/7.0/en/manual/config/items/itemtypes/internal)
- [Zabbix 7.0 — configuração do servidor](https://www.zabbix.com/documentation/7.0/en/manual/appendix/config/zabbix_server)
