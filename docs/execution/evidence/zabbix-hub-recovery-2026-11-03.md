# Recuperação Zabbix → Hub ligada (03/11)

**Achado:** o Hub tinha 105.360 incidentes `open` e nenhum com `ninf_zabbix_status=resolved`. A ação Zabbix "ness.OS Hub - alert ingestion" (id 7) só tinha operação de problema e o media type (id 72) enviava `status:'PROBLEM'` fixo. O worker (`_async_process_recovery`) estava pronto e nunca era chamado.

**Mudança no Zabbix de produção (OK do Ricardo, "siga"):** `infra/scripts/zabbix-hub-recovery.php --apply`
- media type 72: parâmetro novo `event_status={EVENT.STATUS}`; o script envia `RESOLVED` quando vale `RESOLVED`, senão `PROBLEM`;
- ação 7: operação de recuperação que chama o mesmo media type para o usuário do Hub.

**Backup / rollback:** `/var/lib/ness-os/hub-rollout/{mediatype,action}-before-recovery.json` (root 0600) no Zabbix de produção. Rollback: restaurar `script` e `parameters` do media type e apagar a operação de recuperação da ação 7.

**Verificação:** após a mudança, `n_infraops_incident_actions` ganhou `zabbix_recovered` (3 ações, a última às 22:27 UTC).

**Não muda:** o `status` do incidente continua `open` até o GLPI resolver (política em `docs/operations/zabbix-recovery-policy.md`); "aberto de verdade" = `ninf_zabbix_status <> 'resolved'`.

**Pendente:**
1. Ajustar indicadores/telas que contam `status='open'` para considerar `ninf_zabbix_status`.
2. Backfill dos ~30 mil incidentes `problem` cuja recuperação já passou (dry-run primeiro). Os 75 mil anteriores a 12/10 não têm esse campo.
