#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly s3_env="${PSONO_S3_ENV:-/etc/ness-os/backup-s3.env}"
[[ -f ${s3_env} && ! -L ${s3_env} ]] || { echo 'backup environment is unavailable' >&2; exit 2; }
[[ $(stat -c '%u:%a' "${s3_env}") =~ ^0:(400|600)$ ]] || {
  echo 'backup environment must be root-owned and mode 0400 or 0600' >&2
  exit 3
}

set -a
# shellcheck disable=SC1090
. "${s3_env}"
set +a
export RESTIC_REPOSITORY="s3:${CONTABO_S3_ENDPOINT%/}/${CONTABO_S3_BUCKET}/ness-os/psono-prod/psono"
export RESTIC_CACHE_DIR=/var/cache/ness-os-restic

if restic cat config >/dev/null 2>&1; then
  echo 'psono restic repository=already_initialized'
else
  restic init
  echo 'psono restic repository=initialized'
fi
