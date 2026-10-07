# Evidência atual de recuperação AIOps — Fase 0

Coleta somente leitura concluída em 2026-09-26 às 19:07:32 UTC (16:07:32 BRT)
na VPS AIOps `144.91.115.242` (`vmi3409271`), pela identidade nominal
`ness_admin`. `npentest` não foi acessada.

## Backup local

- Conjunto: `20260925T230000-0300`, em
  `/opt/n-infraops/backups/nightly/20260925T230000-0300`.
- `ness-aiops-backup.service` terminou em 25/09 às 23:04:25 BRT com
  `Result=success`, código 0 e estado `inactive/dead` após concluir.
- O marcador `COMPLETED` está presente, vazio, `root:root`, modo `0600`.
- `sha256sum -c SHA256SUMS` aprovou todas as 24 entradas do conjunto.
- Timer local ativo/aguardando; último disparo 25/09 às 23:00 e próximo em
  26/09 às 23:00 BRT. A idade do conjunto era de 17h04 na coleta.

## Cópia externa e restauração isolada

- `ness-aiops-object-storage-backup.service` terminou em 26/09 às 00:30:50 BRT
  com `Result=success` e código 0. O timer está ativo/aguardando; próximo
  disparo em 27/09 às 00:30 BRT.
- O verificador instalado em `/usr/local/sbin/aiops-deployment-remote-verify`
  tem o mesmo SHA-256 do script versionado:
  `bdef3f7d4869f92747e79d74ce70245b06150ea0a32500c4a0ad8e0703a2d5cc`.
- Execução do verificador para o conjunto acima: `deployment_remote_restore=PASS`.
  O snapshot `d66d36f3e5cc4591825fe7587bcea87134b4d8b48696e6e75dd222c935265b0e`
  contém o `backup_set_id` esperado; Restic restaurou 860,216 MiB e verificou
  26 arquivos. Todos os checksums restaurados passaram, assim como as
  verificações de marcador `COMPLETED` e manifesto.
- O restore ocorreu em diretório temporário separado, nunca sobre dados ativos.
  Após o término bem-sucedido, confirmou-se que não restou diretório
  `remote-verify-*` em `/opt/n-infraops/restore-tests`.

## Limites

Esta evidência comprova o conjunto AIOps de 25/09 e o snapshot externo associado.
Ela não atualiza hashes do código/imagens em produção, nem comprova estado atual
do Zabbix ou da UAT. O gate de release continua condicionado à reconciliação
completa, digests imutáveis, CI e ensaio de rollback.

## Revalidação de timers e checksums — 19:40 UTC

Coleta somente leitura por `ness_admin` em 2026-09-26 às 19:40 UTC:

- O conjunto local mais recente segue `20260925T230000-0300`, com marcador
  `COMPLETED` modo `0600`; as 24 entradas de `SHA256SUMS` passaram novamente.
  A idade do conjunto era de aproximadamente 17h36.
- `ness-aiops-backup.service` e `ness-aiops-object-storage-backup.service`
  reportaram `Result=success`, `ExecMainStatus=0` e `ActiveState=inactive` após
  terminar.
- `ness-aiops-backup.timer` está ativo e aponta para 26/09 às 23:00 BRT;
  `ness-aiops-object-storage-backup.timer` está ativo e aponta para 27/09 às
  00:30 BRT.
- Nenhum timer foi disparado manualmente nesta revalidação.
