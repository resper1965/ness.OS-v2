#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="${repo_root}/infra/scripts/ness-object-storage-restic.sh"
systemd_dir="${repo_root}/infra/systemd"

bash -n "${script}"

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
grep -q 'flock -w 14400 9' "${script}"

grep -q -- '-type f -name COMPLETED' "${script}"
grep -q 'SHA256SUMS' "${script}"
grep -q 'check_percent}%"' "${script}"
grep -q -- '--keep-last "${keep_last}"' "${script}"
grep -q 'ness-os/${NESS_BACKUP_HOST_ID}/${dataset}' "${script}"
grep -q 'EnvironmentFile mode must be 0400 or 0600' "${script}"
grep -q '\. "${env_file}"' "${script}"

if grep -Eq '(AKIA[[:alnum:]]{12,}|secret[^=]*=[^[:space:]]+|password[^=]*=[^[:space:]]+)' \
  "${systemd_dir}/ness-object-storage-restic.env.example"; then
  echo "environment example appears to contain a credential" >&2
  exit 1
fi

echo "object-storage restic tooling static checks: PASS"
