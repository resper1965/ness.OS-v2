#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
restic_script="${repo_root}/infra/scripts/ness-object-storage-restic.sh"
remote_script="${repo_root}/infra/scripts/aiops-deployment-remote-verify.sh"
restore_script="${repo_root}/infra/scripts/aiops-isolated-restore-test.sh"
systemd_dir="${repo_root}/infra/systemd"

bash -n "${restic_script}" "${remote_script}" "${restore_script}"

grep -q 'EnvironmentFile=/etc/ness-os/backup-s3.env' \
  "${systemd_dir}"/ness-*-object-storage-backup.service
grep -q 'ReadOnlyPaths=/var/backups/zabbix/nightly' \
  "${systemd_dir}/ness-zabbix-object-storage-backup.service"
grep -q 'ReadOnlyPaths=/opt/n-infraops/backups/nightly' \
  "${systemd_dir}/ness-aiops-object-storage-backup.service"
grep -q 'After=network-online.target ness-zabbix-backup.service' \
  "${systemd_dir}/ness-zabbix-object-storage-backup.service"
grep -q 'After=network-online.target ness-aiops-backup.service' \
  "${systemd_dir}/ness-aiops-object-storage-backup.service"
grep -q 'flock -w 14400 9' "${restic_script}"
grep -q -- '-type f -name COMPLETED' "${restic_script}"
grep -q 'SHA256SUMS' "${restic_script}"
grep -q 'check_percent}%' "${restic_script}"
grep -q -- '--keep-last "${keep_last}"' "${restic_script}"
grep -q 'ness-os/${NESS_BACKUP_HOST_ID}/${dataset}' "${restic_script}"
grep -q 'EnvironmentFile mode must be 0400 or 0600' "${restic_script}"
grep -q '\. "${env_file}"' "${restic_script}"

# The newest local set must select a snapshot tagged with that exact set ID.
# The former dataset-only tag silently selected an older snapshot after a new set.
grep -q 'ness-backup-set-' "${restic_script}"
grep -q 'backup-set-manifest.json' "${restic_script}"
grep -q "grep -Fq -- './backup-set-manifest.json'" "${restic_script}"
grep -Fq '(cd "${backup_set}" && sha256sum -c SHA256SUMS)' "${restic_script}"
grep -q 'ness-backup-set-{set_id}' "${remote_script}"
grep -q 'expected one snapshot for backup_set_id' "${remote_script}"
grep -q 'snapshots --json --host' "${restore_script}"
grep -q 'backup_set_id' "${remote_script}"
grep -Fq "grep -Fq -- './backup-set-manifest.json'" "${remote_script}"
grep -q 'backup_set_id' "${restore_script}"
grep -q -- '--remote' "${restore_script}"

# Reproduce the stale-snapshot case: an older remote ID must not satisfy a new local ID.
snapshot_fixture="$(mktemp)"
selector_script="$(mktemp)"
trap 'rm -f -- "${snapshot_fixture}" "${selector_script}"' EXIT
command -v python3 >/dev/null || { echo 'python3 is required for snapshot selection test' >&2; exit 1; }
printf '%s\n' '[{"id":"old-snapshot","tags":["ness-dataset-aiops","ness-backup-set-20260925T110000-0300"]}]' >"${snapshot_fixture}"
cat >"${selector_script}" <<'PY'
import json, sys
set_id, snapshot_file = sys.argv[1:]
with open(snapshot_file, encoding="utf-8") as source:
    rows = json.load(source)
ids = [row["id"] for row in rows if "ness-dataset-aiops" in row.get("tags", [])
       and f"ness-backup-set-{set_id}" in row.get("tags", [])]
assert len(ids) == 1, f"expected one snapshot for backup_set_id={set_id}, found {len(ids)}"
print(ids[0])
PY
[[ "$(python3 "${selector_script}" '20260925T110000-0300' "${snapshot_fixture}")" == old-snapshot ]] || {
  echo 'matching snapshot ID was not selected' >&2
  exit 1
}
if python3 "${selector_script}" '20260925T120000-0300' "${snapshot_fixture}" >/dev/null 2>&1; then
  echo "stale Restic snapshot incorrectly satisfied a newer local backup_set_id" >&2
  exit 1
fi

if grep -Eq '(AKIA[[:alnum:]]{12,}|secret[^=]*=[^[:space:]]+|password[^=]*=[^[:space:]]+)' \
  "${systemd_dir}/ness-object-storage-restic.env.example"; then
  echo "environment example appears to contain a credential" >&2
  exit 1
fi

echo "object-storage restic tooling static checks: PASS"
