# Zabbix PRD-01 — prontidão da Onda 1 (2026-08-25)

Esta preparação foi executada somente por leitura contra a base restaurada.
Não houve alteração de banco, host, template, coleta ou serviço.

## Escopo priorizado

| Frente | Evidência | Decisão |
| --- | ---: | --- |
| FortiGate por link | 58 falhas `vfs.fs.pfree` em 58 hosts | Consolidar por appliance; não fabricar percentual de disco quando a métrica não existe. |
| FortiGate principal | 344 falhas no `Numen IT Matriz Fortigate 61F Link Vivo wan2` | Confirmar inventário, endpoint e modelo antes de alterar template. |
| Switches com template incorreto | 32 falhas em dois ativos Cavan | Reconciliar no GLPI e substituir somente após confirmar fabricante/modelo/protocolo. |
| Windows | 288 falhas em 76 candidatos | Onda seguinte: primeiro disponibilidade/versão do agente, depois métricas WMI/perfmon. |

## Guardrails para a UAT

1. Manter `zabbix-server` mascarado até a camada web segura e a janela de UAT.
2. Exportar, pela API suportada, hosts, templates, vínculos, tags, macros sem
   valores, triggers e gráficos antes de qualquer troca.
3. Nunca usar SQL para alterar configuração Zabbix; nunca usar `Unlink and
   clear`; não excluir hosts nem histórico.
4. Pilotar apenas um appliance FortiGate com múltiplos links por 24–72 horas,
   com actions, media types e connectors ainda desabilitados.
5. Fazer rollback por relink do template/export, não por reconstrução manual.

## Critério para abrir a execução funcional

O primeiro piloto só pode começar após: autenticação administrativa da nova
instância homologada, HTTPS/borda restrita, export de rollback armazenado e
identidade do ativo confirmada pelo inventário GLPI/owner. A etapa seguinte é
preparar essa UAT segura; nenhuma correção funcional é aplicável com o servidor
corretamente mascarado.
