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
