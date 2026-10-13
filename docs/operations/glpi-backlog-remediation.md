# GLPI — reconciliação segura do backlog

Estado em 13/10/2026: **somente leitura**. A identidade técnica 106 está
desativada após falha comprovada de isolamento entre entidades. Este runbook
não autoriza replay, criação, solução ou exclusão de tickets.

## Entrada e classificação

1. Executar `infra/scripts/glpi_backlog_classify.py` no runtime Hub, com o
   ambiente já provisionado, em páginas de no máximo 100 e cursor crescente.
   O script usa transação PostgreSQL `READ ONLY` e publica apenas totais.
2. Para incidentes com identificador de evento e entidade mapeada, executar
   `infra/scripts/glpi_backlog_reconcile.py` em páginas de até cinco. A busca
   remota usa o marcador completo, entidade explícita e encerra a sessão.
   Erro, 403 ou entidade sem mapeamento **não** significa ticket ausente.
3. Registrar por onda: janela temporal, entidade, contagens por motivo,
   cursor inicial/final, erros e commit/runtime. Não incluir nomes, conteúdo,
   marcadores, tokens ou dados pessoais no relatório público.

Leitura já comprovada: 115 marcadores históricos e 29 recentes não foram
encontrados nas entidades mapeadas; nenhuma escrita ocorreu. Quinze registros
legados sem identificador de evento não têm chave de origem suficiente para
replay idempotente e permanecem em quarentena. A causa dos 29 erros recentes
foi gravada como `RuntimeError` genérico e ainda não está determinada.

| Classe | Próxima ação permitida agora | Condição para escrita futura |
|---|---|---|
| `source_id_missing` | Quarentena e investigação da origem | Identidade estável comprovada e decisão de operação |
| `inconsistent_ticket_audit` | Conferir ticket e ação por leitura | Reparar vínculo, nunca criar segundo ticket por suposição |
| `permission_blocked` | Diagnosticar perfil/entidade sem retry | Isolamento T03 aprovado e credencial mínima ativa |
| `transient_failed_queue_unverified` / `failed_unclassified` | Conferir fila, ação e ticket remoto | Causa corrigida, busca negativa íntegra e retry controlado |
| `retry_exhausted` | Inspecionar falha e ticket remoto | Nova tentativa explícita, limitada e auditada |
| `historical_unclassified` / `recent_unconfirmed` | Aguardar ou reconciliar por leitura | Fonte/entidade/ausência remota comprovadas |
| `non_open_without_ticket` | Verificar recovery e política | Decisão de ciclo de vida; não abrir ticket retrospectivo automaticamente |

## Gate de replay e rollback

Antes de qualquer POST: T03 deve provar negação da rota direta e da entidade
descendente; a identidade mínima deve estar ativa somente no percurso privado;
release por digest, rollback, busca paginada íntegra e auditoria devem estar
verificados. A conta Hub existente não recebe privilégios adicionais.

Aplicar no máximo cinco incidentes por onda, exportando IDs e vínculos em
evidência protegida. Para cada incidente: buscar marcador e entidade, reutilizar
ticket único existente ou criar uma vez, confirmar ID/vínculo/ação e repetir a
consulta para provar idempotência. Qualquer 403, duplicata, paginação incerta,
falha de logout ou entidade divergente aborta a onda; não prosseguir para o
próximo item. O rollback da onda interrompe novos envios e restaura o vínculo
local somente se a evidência demonstrar erro; ticket já criado no GLPI não é
apagado automaticamente. Preservar histórico e abrir correção individual.

Nenhuma contagem baixa por exclusão/encerramento em massa. A operação aprova
separadamente a política de transições de tickets históricos.
