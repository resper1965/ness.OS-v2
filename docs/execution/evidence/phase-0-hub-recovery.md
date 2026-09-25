# Fase 0 — evidência de recuperação externa do Hub

**Resultado: PASS** — conjunto local atual, cópia Contabo Object Storage e restauração isolada estão associados pelo mesmo `backup_set_id`.

## Identificação

- VPS: AIOps `vmi3409271` (`aiops-prod`). A VPS `npentest` ficou fora do escopo.
- Conjunto local: `20260925T122220-0300` (`backup_set_id` no `backup-set-manifest.json`).
- Caminho local: `/opt/n-infraops/backups/nightly/20260925T122220-0300`.
- Snapshot Restic: `880d484679f486194fa6078b798e2efdaeb88ecbc22c66e41bbab1b30ea766d9`.
- Tags do snapshot: `ness-dataset-aiops`, `ness-backup-set-20260925T122220-0300`.
- Tamanho informado pelo Restic: `859.017 MiB` (`900,703,792` bytes processados).
- SHA-256 do manifesto local: `4ec8960fed6f501539c67b58866a22944c33c6f7f68f079bd9df2ccb94d7948f`.
- SHA-256 de `SHA256SUMS`: `ac1bcf34bbdd29b78118aa516e39b9bf8c41672ced0804b95519d9a8a5698f1e`.

## Execução em UTC

- Backup local iniciado conforme timestamp do conjunto: `2026-09-25T15:22:20Z`.
- Backup local concluído: `2026-09-25T15:28:19Z`; `ness-aiops-backup.service` terminou com `Result=success`, `ExecMainStatus=0` e `ActiveState=inactive`.
- Cópia externa do Restic: snapshot criado em `2026-09-25T15:31:30.314303Z`; serviço terminou por volta de `2026-09-25T15:31:42Z`, com `Result=success` e `ExecMainStatus=0`.
- Verificação do snapshot remoto: PASS. O snapshot exato foi restaurado com `restic restore --verify`; 28 entradas (arquivos e diretórios), 859.017 MiB, 26 arquivos verificados. Checksums relativos e manifesto confirmaram o ID `20260925T122220-0300`.
- Restauração isolada iniciada em `2026-09-25T15:33:18Z` e concluída aproximadamente em `2026-09-25T15:36:20Z` (182 segundos). Comando: `aiops-isolated-restore-test --remote`.

## Sondas da restauração isolada

- PostgreSQL: 4 bancos restaurados; 16 roles; contagens de relações e proprietários consultadas em `authentik`, `evolution`, `nessops` e `postgres`.
- MariaDB/GLPI: 466 tabelas; as duas tabelas de projetos (`glpi_projects`, `glpi_projecttasks`) presentes.
- Arquivos: 16 arquivos compactados extraídos.
- Rede dos containers temporários: `none`.
- Limpeza: 0 containers e 0 volumes `ness_restore` permaneceram após o job. 16 containers de produção estavam em execução na verificação final.
- Espaço livre após a restauração: 307 GiB em `/`.

## Avisos observados

- `pg_dump` avisou sobre chaves estrangeiras circulares em `continuous_agg` (TimescaleDB). O dump foi criado, listado por `pg_restore` e os quatro bancos foram restaurados e consultados com sucesso.
- `tar` avisou que alguns arquivos GLPI têm timestamps futuros em relação ao relógio da VPS. A extração dos 16 arquivos terminou com sucesso e os checksums do snapshot foram aprovados.

Nenhum valor de credencial foi incluído nesta evidência.
