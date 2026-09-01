#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }
readonly env_file=/etc/ness-os/backup-s3.env
readonly target=/var/lib/ness-os/restic-restore-verify

set -a
. "${env_file}"
set +a
export RESTIC_REPOSITORY="s3:${CONTABO_S3_ENDPOINT%/}/${CONTABO_S3_BUCKET}/ness-os/${NESS_BACKUP_HOST_ID}/zabbix"
export RESTIC_CACHE_DIR=/var/cache/ness-os-restic

rm -rf "${target}"
install -d -m 0700 -o root -g root "${target}"
restic restore latest --target "${target}"
backup_set="$(find "${target}" -type f -name SHA256SUMS -printf '%h\n' | head -n 1)"
[[ -n "${backup_set}" ]]
(
  cd "${backup_set}"
  sha256sum -c SHA256SUMS
)
find "${backup_set}" -type f -printf '%s\n' | awk '{ total += $1 } END { print "restored_bytes=" total }'
rm -rf "${target}"
echo 'external_restore=PASS'
