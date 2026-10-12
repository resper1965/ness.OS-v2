# Zabbix — janela excepcional autorizada

Autorização direta do usuário: 24 horas de janela; prioridade de entrega
produtiva em quatro horas, permitindo Cavan como piloto.

Registro: 12/10/2026 11:47:35 BRT (14:47:35 UTC). Limite operacional adotado:
13/10/2026 11:47:35 BRT. Após esse limite volta a janela 22:00–00:00 BRT.
A meta de quatro horas não elimina rollback, isolamento ou evidência de corte.
Observação 24–72h/D+1/D+3/D+7 continua posterior, sem aceite fictício imediato.

Origem: Zabbix 7.0.27 e MariaDB ativos. Último conjunto existente:
20261011T220025-0300, snapshot externo f0b19cf8 de 12/10 às 05:32 BRT.
Destino: backup offline de rollback 20261012T112805-0300 terminou com sucesso
e COMPLETED. Nenhum novo dump de teste será iniciado nesta preparação.

Credencial válida encontrada no consumidor Hub, permitindo leitura da origem.
Os cinco hosts Cavan 10873,10874,10877,10878,10885 já têm tags tenant, site,
environment, scope, owner, role e technology na origem. O banco antigo da UAT
não tinha essas tags. Prioridade passa a sincronizar a UAT com a origem;
não aplicar o pacote antigo de tags sobre uma baseline corrente diferente.

Staging do snapshot f0b19cf8 iniciado pela unidade
ness-zabbix-migration-stage-20261012. Restore no banco definitivo ainda depende
de staging íntegro e preservação do rollback. Origem continua coletando até o
freeze final de corte; destino permanece mascarado/inativo para impedir dupla
coleta. Toda evidência deve distinguir preparação, aplicação e produção.

Staging concluído às 11:54:38 BRT: dump 5.261.041.778 bytes, SHA256SUMS e gzip
aprovados. Snapshot restaurou seu conteúdo na raiz de restic-f0b19cf8. A primeira
tentativa de refresh usou caminho inexistente e abortou antes de tocar o banco;
caminho corrigido após inspeção. Importação corrente na unidade
ness-zabbix-refresh-validated-20261012, PID inicial 556425.

Leitura corrente na origem via credencial runtime do Hub e leitura SQL restrita:
os cinco hosts Cavan possuem um template vinculado cada. Itens não suportados:
10873=1, 10874=1, 10877=2, 10878=0, 10885=0. A ausência de parentTemplates
na resposta do token Hub não comprova ausência de template; a consulta de banco
confirmou os vínculos. O pacote antigo de correção não deve sobrescrever isso.

Branding nativo aplicado no destino, usando `local/conf/brand.conf.php` e
logos oficiais já existentes, sem editar core. Rollback:
`/var/lib/ness-os/restore-evidence/branding-20261012T120055-0300`.
PHP lint e comparação dos assets passaram; inspeção da UI depende de terminar
a importação. Publicação e aceitação visual ainda não estão declaradas.

O destino possui 48 GiB RAM e buffer pool 16 GiB. Durante a importação isolada,
`innodb_flush_log_at_trx_commit` mudou temporariamente de 1 para 2; a unidade
ness-zabbix-reset-durability-20261012 está enfileirada após o import para voltar
a 1, inclusive se a importação falhar. A promoção exige confirmar 1. Risco
restrito ao dump em importação: uma queda pode perder até o último segundo de
transações e exigir reimportação do snapshot imutável; origem não foi alterada.
