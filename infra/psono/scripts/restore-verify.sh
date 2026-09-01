#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly s3_env="${PSONO_S3_ENV:-/etc/ness-os/backup-s3.env}"
readonly target="${PSONO_RESTORE_VERIFY_ROOT:-/var/lib/ness-os/psono-restore-verify}"

[[ ${target} == /var/lib/ness-os/psono-restore-verify ]] || {
  echo 'unexpected restore verification target' >&2
  exit 2
}
[[ -f ${s3_env} && ! -L ${s3_env} ]] || { echo 'backup environment is unavailable' >&2; exit 3; }

set -a
# shellcheck disable=SC1090
. "${s3_env}"
set +a
export RESTIC_REPOSITORY="s3:${CONTABO_S3_ENDPOINT%/}/${CONTABO_S3_BUCKET}/ness-os/psono-prod/psono"
export RESTIC_CACHE_DIR=/var/cache/ness-os-restic

rm -rf -- "${target}"
install -d -m 0700 -o root -g root "${target}"
trap 'rm -rf -- "${target}"' EXIT
restic restore latest --target "${target}"

set_dir="$(find "${target}" -type f -name COMPLETED -printf '%h\n' | head -n1)"
[[ -n ${set_dir} && -f ${set_dir}/SHA256SUMS ]] || { echo 'completed backup set not found' >&2; exit 4; }
(
  cd "${set_dir}"
  sha256sum --check SHA256SUMS
  docker exec -i ness-psono-db pg_restore --list <psono.pgdump >/dev/null
  tar --list --gzip --file configuration.tar.gz >/dev/null
)
echo 'psono_restore_verify=PASS'
