# Decisão de engenharia — estratégia das ondas de polimento Zabbix

**Estado:** direção de planejamento selecionada; nenhuma mudança de produção
autorizada por este registro.

**Data:** 2026-09-25. **Base:** delegação do usuário para seguir o plano e tomar
decisões pequenas; recomendação D-PAC-1 em
`docs/execution/project-stage-2026-09-17.md`.

## Decisão

Seguir a opção de **ondas pequenas controladas pela API suportada**, com dry-run,
pré-condição de estado, idempotência e rollback por export/relink. Não usar SQL
direto, `Unlink and clear`, exclusão de hosts nem limpeza de histórico para reduzir
os números do dashboard.

## Sequência proposta

1. Após o gate da Fase 0 passar, produzir um baseline atual e somente leitura de
   hosts, itens não suportados, triggers desconhecidas, tags/templates e problemas.
2. Selecionar o primeiro grupo a partir de inventário confirmado. Priorizar o
   piloto FortiGate/link da Onda A; corrigir fabricante, modelo, tenant, owner e
   template pela API, com export de rollback antes de cada escrita.
3. Limitar a primeira execução a no máximo cinco hosts críticos e observar por
   24–72 horas. Manter actions, media types e connectors desabilitados durante UAT.
4. Só ampliar o lote após confirmar paridade de métricas, ausência de duplicidade
   de coleta e nenhuma regressão em outras categorias. Tratar Windows e
   triggers/escalations em ondas posteriores, com novo baseline por onda.

Os IDs dos hosts e as alterações exatas serão escolhidos pelo relatório atual,
nunca pelos totais históricos dos documentos de agosto/setembro.

## Condições de entrada

- Gate da Fase 0 aprovado; hoje permanece `FAIL`.
- Destino de UAT seguro e autenticado; não usar o Zabbix canônico como laboratório.
- Backup/restauração e rollback válidos antes de cada escrita.
- Identidade do ativo confirmada no GLPI e estado atual comparado imediatamente
  antes da operação.

O cronograma antigo que previa uma onda de triggers em 27/09 não é autorização
para executá-la: a evidência da Onda 2 não está atualizada e as condições de
entrada acima ainda não foram satisfeitas. A próxima onda funcional será
reagendada depois do baseline corrente e do gate aprovado.
