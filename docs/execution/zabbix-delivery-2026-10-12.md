# Zabbix — entrega completa em execução

Prioridade exclusiva autorizada em 12/10/2026. Owner técnico: plataforma.
G2 segue aberto nas issues; implementação isolada continua. Corte produtivo
exige gates e janela 22:00–00:00 BRT, sem presumir a exceção de agosto vigente.

## Ordem e evidências de aceite

1. Backup destino: unidade offline funcional, COMPLETED/checksum/gzip, cópia
   externa e restore isolado atual; origem preservada.
2. Baseline origem/destino: inventário, templates, unsupported, fila, NVPS,
   busy, proxies e ações; origem somente na janela para leitura intensiva.
3. Qualidade: piloto interno e Cavan Matriz, export/rollback, cinco ativos por
   lote, tags e templates completos, redução FortiGate e observação 24–72h.
4. Operação: HTTPS/SAML, contas nominais, API mínima, tenant e break-glass.
5. Visibilidade: painéis NOC, coleta, capacidade e serviços; dados e timestamps
   reconciliados, mapas com localidade validada.
6. Branding: camada suportada/reversível ness., sem editar core, pt-BR e
   validação desktop/móvel.
7. Corte: GO e gates, snapshot final, origem congelada, DNS/proxies autorizados,
   nenhuma dupla coleta; ações reais bloqueadas no smoke test.
8. Sustentação: D+1/D+3/D+7, backup/restore, runbooks e preservação da origem.

## Incremento executado

Corrigida em zbx-prd-01 a unidade de backup que exigia iniciar o servidor
mascarado. O drop-in inicial não removeu a dependência efetiva; foi substituído
pela unidade offline completa versionada. A dependência efetiva agora exige
somente MariaDB e componentes básicos de systemd.

Rollback da unidade e script:
`/var/lib/ness-os/change-backups/offline-backup-20261012`.
Unidade anterior: `ness-zabbix-backup.service`; restaurar essa cópia só na
transição aprovada para produção, pois ela exige servidor ativo.

Timer recuperado e ativo. Backup iniciou em 12/10 às 11:28 BRT por systemd,
com timeout de três horas e prioridade reduzida. Ainda não é PASS de backup:
aguarda COMPLETED, checksum, gzip e sucesso terminal. Zabbix permanece
mascarado/inativo, sem listener 10051. Ações/mídias/conectores continuam zero
conforme baseline offline desta data.

Testes locais: contrato offline backup e bash syntax passaram. Nenhuma
alteração na origem, DNS ou coleta ocorreu nesta execução.
