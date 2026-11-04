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
2. Ajustar o contador do frontend: feito em #149 e promovido em 04/11 (`ninf-frontend@sha256:f4afa04a6f48076cd7a899cd16980ddd43a1c0ed856111e47e4f2a6ee7e9fb6f`, commit `1b76de6`). Rollback: `NINF_FRONTEND_IMAGE` de volta para `@sha256:1051d84f…` no `.env` da release e recriar só o `frontend`.

**Backfill (04/11, OK do Ricardo):** dry-run sobre 30.161 incidentes `problem` (29.149 recuperados, 319 ainda abertos, 693 sem evento no Zabbix). Lote de 500 (279 gravados) e depois `--apply` completo: `examined=29881 recovered=28872 still_open=316 not_found=693`. Conferência: 29.151 incidentes com a tag `ninf_zabbix_backfill`, 29.151 ações `actor_source='backfill'`, todos com `status='open'` (não alterado). Na conferência restavam 1.006 `open` com `ninf_zabbix_status=problem`, contra 1.009 esperados pela leitura do backfill (316 abertos + 693 sem evento). A diferença de 3 é compatível com incidentes que se recuperaram ao vivo entre as duas leituras; não confirmei incidente a incidente. Rollback: tag `ninf_zabbix_status`=problem, remover `ninf_zabbix_recovered_at` e `ninf_zabbix_backfill`, apagar as ações `backfill`, sempre pelos ids da tag.
