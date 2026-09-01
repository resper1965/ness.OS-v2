#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly stack_dir="${PSONO_STACK_DIR:-/opt/ness-os-psono}"
readonly backup_root="${PSONO_BACKUP_ROOT:-/var/backups/ness-os/psono}"
readonly s3_env="${PSONO_S3_ENV:-/etc/ness-os/backup-s3.env}"
readonly stamp="$(date +%Y%m%dT%H%M%S%z)"
readonly target="${backup_root}/${stamp}"

[[ -f ${s3_env} && ! -L ${s3_env} ]] || { echo 'backup environment is unavailable' >&2; exit 2; }
[[ $(stat -c '%u:%a' "${s3_env}") =~ ^0:(400|600)$ ]] || {
  echo 'backup environment must be root-owned and mode 0400 or 0600' >&2
  exit 3
}
[[ -f ${stack_dir}/runtime/settings.yaml && \
   -f ${stack_dir}/runtime/config.json && \
   -f ${stack_dir}/runtime/postgres.env && \
   -f ${stack_dir}/docker-compose.aiops.yml && \
   -f /etc/ness-os/psono.env ]] || {
  echo 'psono runtime configuration is unavailable' >&2
  exit 4
}

install -d -m 0700 -o root -g root "${target}"
docker exec ness-psono-db pg_dump -U psono -d psono -Fc >"${target}/psono.pgdump"
docker exec -i ness-psono-db pg_restore --list <"${target}/psono.pgdump" >/dev/null
tar --create --gzip --file "${target}/configuration.tar.gz" \
  -C "${stack_dir}" \
  runtime/settings.yaml runtime/config.json runtime/postgres.env \
  Caddyfile docker-compose.yml docker-compose.aiops.yml \
  -C / etc/ness-os/psono.env
(
  cd "${target}"
  sha256sum psono.pgdump configuration.tar.gz >SHA256SUMS
  sha256sum --check SHA256SUMS
  printf 'completed_at=%s\n' "$(date --iso-8601=seconds)" >COMPLETED
)

set -a
# shellcheck disable=SC1090
. "${s3_env}"
set +a
export RESTIC_REPOSITORY="s3:${CONTABO_S3_ENDPOINT%/}/${CONTABO_S3_BUCKET}/ness-os/psono-prod/psono"
export RESTIC_CACHE_DIR=/var/cache/ness-os-restic
restic backup "${target}" --tag ness-os --tag psono --tag completed
restic check
echo "psono_backup=PASS set=${stamp}"
