#!/usr/bin/env bash
# Run as root on zbx-prd-01. Restores a validated external snapshot into staging only.
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly snapshot_id="${1:?usage: zabbix-object-storage-stage-restore.sh SNAPSHOT_ID}"
readonly stage="/var/lib/ness-os/restore-input/restic-${snapshot_id}"
readonly log=/var/log/ness-os/zabbix-object-restore.log
readonly env_file=/etc/ness-os/backup-s3.env

[[ -r "${env_file}" ]] || { echo 'backup environment is unavailable' >&2; exit 2; }
[[ ! -e "${stage}" ]] || { echo "staging path already exists: ${stage}" >&2; exit 3; }

install -d -m 0750 -o root -g root /var/log/ness-os /var/lib/ness-os/restore-input
exec > >(tee -a "${log}") 2>&1

echo "phase=start snapshot=${snapshot_id} time=$(date --iso-8601=seconds)"
systemctl is-enabled zabbix-server || true
systemctl is-active zabbix-server || true

set -a
. "${env_file}"
set +a
export RESTIC_REPOSITORY="s3:${CONTABO_S3_ENDPOINT%/}/${CONTABO_S3_BUCKET}/ness-os/zabbix-prod/zabbix"
export RESTIC_CACHE_DIR=/var/cache/ness-os-restic
install -d -m 0700 -o root -g root "${stage}" "${RESTIC_CACHE_DIR}"

echo 'phase=restic-check'
restic check
echo "phase=restore snapshot=${snapshot_id}"
restic restore "${snapshot_id}" --target "${stage}"

backup_set="$(find "${stage}" -type f -name SHA256SUMS -printf '%h\n' | head -n 1)"
[[ -n "${backup_set}" ]] || { echo 'SHA256SUMS not found' >&2; exit 4; }
echo 'phase=sha256'
( cd "${backup_set}" && sha256sum -c SHA256SUMS )

dump="$(find "${backup_set}" -type f -name 'dbzabbix*.sql.gz' -print -quit)"
[[ -n "${dump}" ]] || { echo 'zabbix dump not found' >&2; exit 5; }
echo 'phase=gzip'
gzip -t "${dump}"

printf 'phase=complete backup_set=%s dump_bytes=%s time=%s\n' \
  "${backup_set}" "$(stat -c %s "${dump}")" "$(date --iso-8601=seconds)"
