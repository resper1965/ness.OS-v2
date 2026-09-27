# AIOps backup and external restore verification — 2026-09-27

**Collected:** 2026-09-27 15:31 UTC (12:31 BRT)

**Host:** AIOps `144.91.115.242`, instance `vmi3409271`, via `ness_admin`.
**Scope:** verify current local backup, timer/service results, matching object-storage snapshot, isolated restore, and temporary-directory cleanup. No live application data or services were modified.

## Local backup

- Backup set: `20260926T230011-0300`.
- `COMPLETED` marker and `SHA256SUMS` are present; marker owner/mode are root-only (`root:root`, `0600`).
- `sha256sum -c SHA256SUMS` passed.
- `ness-aiops-backup.service`: `Result=success`, `ExecMainStatus=0`; local timer is active. The 26/09 run completed at 23:04:28 BRT; next timer is 27/09 at 23:00 BRT.

## External copy and restore

- `ness-aiops-object-storage-backup.service`: `Result=success`, `ExecMainStatus=0`; timer is active. The latest run was 27/09 at 00:30:10 BRT.
- The installed verifier's normalized SHA-256 matches the repository version: `bdef3f7d4869f92747e79d74ce70245b06150ea0a32500c4a0ad8e0703a2d5cc`.
- Verifier result: `deployment_remote_restore=PASS`, backup set `20260926T230011-0300`, Restic snapshot `4ca602426be75a75ebe7b44210e08ffb2ed1f7417e586efe302361ad1d23f482`.
- Restic restored 862.761 MiB; `--verify` and all 26 file checks passed. The verifier exited 0. A subsequent check found no remaining `remote-verify-*` temporary directory.
- Next external timer: 28/09 at 00:30 BRT.

## Limits

This proves current AIOps/Hub backup and its external copy only. It does not refresh the Zabbix backup evidence, production file hashes or image digests, and does not approve release or cutover. Phase 0 remains **FAIL**.
