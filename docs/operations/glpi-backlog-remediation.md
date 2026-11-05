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
| `transient_failed_queue_unverified` / `failed_unclassified` | Conferir fila, ação e ticket remoto | Causa corrigida e desfecho do POST comprovado; busca negativa após timeout não prova ausência do ticket |
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

Se o POST puder ter sido aceito mas a resposta se perder, colocar o incidente
em quarentena: não repetir POST por busca negativa imediata nem por expiração
do lock. Reconciliar remotamente e registrar o desfecho antes de nova tentativa.
A branch candidata grava uma reserva única `(entidade, fingerprint)` **antes**
do POST; se a busca ainda vier vazia, tentativas posteriores só consultam e
não reenviam. O esquema `003_glpi_ticket_post_reservations.sql` também integra
o caminho de upgrade idempotente `app.migrate` e foi ensaiado
em PostgreSQL descartável; não foi aplicado ao banco produtivo. Antes de
promover, aplicar o esquema aditivo, verificar a tabela/PK e só então iniciar
o worker novo. Se houver retorno à versão antiga, parar primeiro os envios de
ticket: o worker antigo não consulta reservas. Não apagar reservas no rollback;
liberá-las individualmente exige prova de que nenhum POST foi aceito.
Ensaio da função real com PostgreSQL descartável confirmou um único POST
apesar de duas buscas vazias e reaparecimento posterior do ticket; não houve
contato com GLPI real. T04/replay produtivo permanecem bloqueados até release,
migração e reconciliação real.

Nenhuma contagem baixa por exclusão/encerramento em massa. A operação aprova
separadamente a política de transições de tickets históricos.

## Leitura de 05/11/2026 (somente leitura, nenhuma escrita)

`glpi_backlog_classify.py` em páginas de 500 sobre `deskmanager_ticket_id IS NULL`: 949 incidentes, todos `open`, criados entre 10/07 e 27/10/2026. Nada novo entrou depois de 27/10: não há falha de integração gerando entradas hoje.

| Classe | Qtde | Origem |
|---|---|---|
| `failed_unclassified` | 819 | Último evento `ticket_failed` com `error=RuntimeError` genérico, todos criados em outubro (período da falha de isolamento e da identidade técnica 106 desativada). Causa ainda não determinada |
| `historical_unclassified` | 115 | Marcadores históricos não encontrados nas entidades mapeadas (igual à leitura de 13/10) |
| `source_id_missing` | 15 | Legados sem identificador de evento; permanecem em quarentena |

Os 819 não são ausência provada de ticket: erro genérico e busca negativa não provam que o POST falhou. Próximo passo permitido: `glpi_backlog_reconcile.py` em páginas de até cinco, para separar "ticket existe e falta vínculo" de "ticket não existe". Replay (POST) continua bloqueado pelo gate acima e pede decisão de operação.

Inventário sem ativo: dos 510 incidentes do manifesto T06 de 03/11, hoje 11 incidentes do Hub (de 110.075) estão sem `asset_id`, em 7 `host_id` de teste ou sintéticos (10001, 50001, 50004–50006, 10978 e 1 sem host); não há ativo real a cadastrar. O restante foi ligado.
