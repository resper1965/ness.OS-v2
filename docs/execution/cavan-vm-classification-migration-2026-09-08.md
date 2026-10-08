# Classificação das VMs Cavan — evidência de pré-migração

Estado: migração aplicada e verificada em produção em 08/09/2026, 22:16–22:18 UTC.
As seções de pré-verificação abaixo preservam o estado anterior à mudança.

## Identidades verificadas

| Host Zabbix | Origem GLPI | Nome | Entidade | Local |
| --- | --- | --- | --- | --- |
| 10882 | NetworkEquipment 120 | VMAPP02 | 8 — Cavan | 2 |
| 10883 | NetworkEquipment 121 | VMAPH01 | 8 — Cavan | 2 |
| 10884 | NetworkEquipment 122 | VMAPP01 | 8 — Cavan | 2 |

Os três registros estão ativos, recursivos e possuem UUID distintos. O modelo
atual é `Network Device`, ID 3; nenhum ComputerModel tem esse nome. Esse valor
não representa o modelo de uma VM e não deve ser convertido pelo mesmo ID
numérico. Fabricante, UUID, comentários e demais campos constam do snapshot.

O verificador `infra/scripts/glpi-cavan-vm-migration-audit.php` foi executado no
GLPI de produção após validação `php -l`. Resultado: três ativos, nenhum marcador
duplicado, nenhum vínculo operacional e um conjunto de referências contendo três
registros de histórico (`glpi_logs`, IDs 1316–1318). A busca cobre todas as tabelas
GLPI com pares itemtype/items_id, variantes _1/_2 e referências diretas
networkequipments_id. Novos vínculos fazem a pré-verificação falhar com código 2.

Snapshot completo, protegido com permissão 0600 no servidor:
`/opt/n-infraops/rollback/recovery-20260908/cavan-vm-migration-audit-20260908.json`.
O script recusa sobrescrever evidência anterior. Nenhum registro de ativo foi
alterado nesta etapa.

## Leitores, escritores e janela de transição

- O reconciliador `app/backend/app/integrations/cmdb_sync.py` usa o marcador
  `Zabbix Host ID`, exige uma correspondência única na entidade e atualiza a mesma
  linha Asset do hub. Não deve recriar a identidade do hub nem perder Incident.asset_id.
- `GLPIClient.list_items` usa a coleção REST sem solicitar a lixeira. O código
  instalado `src/Glpi/Api/API.php`, método getItems, define is_deleted=false e
  filtra a coluna is_deleted por esse valor. Portanto, o registro histórico na
  lixeira não deve concorrer com o Computer ativo na reconciliação.
- Os workers de alertas leem glpi_itemtype/glpi_item_id das tags do Asset do hub
  para vincular novos tickets. A atualização do GLPI e do PostgreSQL não constitui
  uma transação única: é necessário coordenar os consumidores e o reconciliador
  durante essa janela e preservar os eventos na fila.
- A busca no código instalado não identificou um conversor nativo entre
  NetworkEquipment e Computer. Não presumir que trocar itemtype em SQL transfere
  corretamente histórico, campos ou relações.

## Procedimento de execução e reversão

1. Reexecutar o preflight imediatamente antes da escrita e guardar nova evidência;
   abortar se surgirem relações, duplicidade, mudança de entidade ou de ciclo de vida.
2. Preparar aplicador idempotente com modelos nativos GLPI, notificações desativadas
   e transação: criar Computers na entidade 8, preservar campos compatíveis e
   identidade monitorada, registrar a referência ao histórico original. Não inferir
   fabricante/modelo, sistema operacional ou criticidade ausentes.
3. Coordenar os consumidores para impedir criação de tickets com o mapeamento
   antigo durante a troca. Eventos recebidos devem continuar enfileirados.
4. Manter os NetworkEquipment na lixeira, com histórico intacto; não purgar.
   Reconciliar o hub preservando os IDs internos dos Assets e dos incidentes.
5. Verificar marcador único por host, entidade/local, ausência de vínculos órfãos,
   histórico original, replay sem novas criações e retomada saudável dos workers.
6. Reversão: restaurar os registros originais, retirar os novos Computers da
   seleção ativa, reconciliar as mesmas identidades do hub e verificar os vínculos.
   Se novos tickets/contratos/documentos surgirem, a reversão deve exigir tratamento
   explícito desses vínculos; não removê-los automaticamente.

## Resultado da execução

Aplicador: `infra/scripts/glpi-cavan-vm-migrate.php`. Coordenação dos consumidores:
`infra/scripts/hub-cavan-vm-cutover.sh`. Validações de sintaxe PHP e Bash aprovadas.
O ensaio `--rehearse` criou os três Computers, validou campos/histórico e desfez a
transação. Uma consulta posterior confirmou que o estado original continuava ativo.

Na aplicação definitiva, os dois workers receberam TERM e encerraram normalmente;
nenhuma tarefa foi terminada à força e nenhuma fila foi apagada. O timer de CMDB
ficou pausado durante a janela. Um novo preflight confirmou ausência de vínculos
antes da transação. Todos os registros foram alterados pelos modelos nativos GLPI.

| Host | Computer ativo | NetworkEquipment preservado na lixeira | Asset do hub preservado |
| --- | --- | --- | --- |
| 10882 | 105 | 120 | 190 |
| 10883 | 106 | 121 | 191 |
| 10884 | 107 | 122 | 192 |

Nome, UUID, entidade 8, local 2 e campos comuns foram preservados. Modelo genérico
`Network Device` não foi reaproveitado como modelo de computador. O comentário dos
Computers identifica explicitamente o registro histórico de origem. Os três logs
originais foram comparados integralmente e permaneceram inalterados.

O replay do aplicador retornou `created: []`, mantendo IDs 105/106/107. A leitura
pela API GLPI usada pelo hub confirmou que os Computers estão visíveis na entidade
Cavan e que os antigos NetworkEquipment não aparecem na coleção ativa. A consulta
PostgreSQL confirmou os mesmos Assets 190/191/192; não havia incidentes associados
a essas três identidades antes ou depois da troca.

Reconciliação: 255 ativos mapeados, 446 incidentes associados no conjunto completo;
somente as duas exclusões conhecidas (10962 sem cliente mapeado e 10978 sintético).
Os dois workers e o timer de CMDB voltaram à execução. Healthcheck de
22:17:54 UTC: Zabbix/GLPI/workers/delivery `ok`, três filas vazias, zero falhas,
zero retries, zero incidentes sem ticket acima de cinco minutos e zero resoluções pendentes.

Evidências protegidas em `/opt/n-infraops/rollback/recovery-20260908/`:

- `cavan-vm-before-20260908T221647Z.json`: snapshot imediatamente anterior.
- `cavan-vm-applied-20260908T221647Z.json`: IDs criados.
- `cavan-vm-replay-20260908T221647Z.json`: idempotência.
- `cavan-vm-hub-20260908T221647Z.json`: reconciliação após a troca.
- `cavan-vm-rollback-rehearsal-20260908.json`: reversão pelos modelos nativos
  executada dentro de uma transação e desfeita ao final. A consulta após o ensaio
  confirmou Computers 105–107 ativos e NetworkEquipment 120–122 na lixeira.

O ensaio de reversão aprovou as alterações GLPI sem efetivar retorno ao cadastro
antigo. Uma reversão efetiva continua exigindo coordenar consumidores e reconciliar
o hub; vínculos novos fazem o aplicador abortar em vez de descartá-los.

Esta entrega encerra a correção de classificação dessas três VMs; os demais
requisitos do inventário Cavan e do programa continuam na matriz de aceite.
