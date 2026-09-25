#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

fail() {
  echo "ness object-storage backup: $*" >&2
  exit 1
}

[[ ${EUID} -eq 0 ]] || fail "must run as root"

readonly action="${1:-}"
readonly dataset="${2:-}"
readonly env_file="${NESS_RESTIC_ENV_FILE:-/etc/ness-os/backup-s3.env}"

[[ "${action}" == "init" || "${action}" == "backup" ]] || \
  fail "usage: $0 {init|backup} {zabbix|aiops}"

case "${dataset}" in
  zabbix)
    readonly backup_root="/var/backups/zabbix/nightly"
    readonly local_lock="/run/lock/ness-zabbix-backup.lock"
    ;;
  aiops)
    readonly backup_root="/opt/n-infraops/backups/nightly"
    readonly local_lock="/run/lock/ness-aiops-backup.lock"
    ;;
  *) fail "dataset must be zabbix or aiops" ;;
esac

for command in find flock install restic sha256sum sort stat; do
  command -v "${command}" >/dev/null || fail "missing command: ${command}"
done

[[ -f "${env_file}" && ! -L "${env_file}" ]] || \
  fail "EnvironmentFile must be a regular, non-symlink file: ${env_file}"
[[ "$(stat -c '%u' "${env_file}")" == "0" ]] || \
  fail "EnvironmentFile must be owned by root"
case "$(stat -c '%a' "${env_file}")" in
  400|600) ;;
  *) fail "EnvironmentFile mode must be 0400 or 0600" ;;
esac

# Loading the root-only file here also makes the deliberate `init` command
# usable outside systemd. The example contains shell-compatible assignments.
set -a
# shellcheck disable=SC1090
. "${env_file}"
set +a

: "${CONTABO_S3_ENDPOINT:?CONTABO_S3_ENDPOINT is required}"
: "${CONTABO_S3_BUCKET:?CONTABO_S3_BUCKET is required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD is required}"
: "${NESS_BACKUP_HOST_ID:?NESS_BACKUP_HOST_ID is required}"

[[ "${CONTABO_S3_ENDPOINT}" =~ ^https://[^/]+/?$ ]] || \
  fail "CONTABO_S3_ENDPOINT must be one HTTPS origin without a path"
[[ "${CONTABO_S3_BUCKET}" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] || \
  fail "CONTABO_S3_BUCKET is not a valid S3 bucket name"
[[ "${NESS_BACKUP_HOST_ID}" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || \
  fail "NESS_BACKUP_HOST_ID must be a stable lowercase host identifier"

readonly keep_last="${RESTIC_KEEP_LAST:-14}"
readonly check_percent="${RESTIC_CHECK_PERCENT:-5}"
[[ "${keep_last}" =~ ^[1-9][0-9]*$ ]] || \
  fail "RESTIC_KEEP_LAST must be an integer greater than zero"
[[ "${check_percent}" =~ ^[1-9][0-9]?$|^100$ ]] || \
  fail "RESTIC_CHECK_PERCENT must be between 1 and 100"

export RESTIC_REPOSITORY="s3:${CONTABO_S3_ENDPOINT%/}/${CONTABO_S3_BUCKET}/ness-os/${NESS_BACKUP_HOST_ID}/${dataset}"
export RESTIC_CACHE_DIR="${RESTIC_CACHE_DIR:-/var/cache/ness-os-restic}"
readonly snapshot_tag="ness-dataset-${dataset}"

install -d -o root -g root -m 0700 "${RESTIC_CACHE_DIR}"

exec 8>"/run/lock/ness-object-storage-restic.lock"
flock -n 8 || fail "another object-storage backup is already running"

if [[ "${action}" == "init" ]]; then
  restic init
  restic check
  exit 0
fi

[[ -d "${backup_root}" ]] || fail "backup root not found: ${backup_root}"

# The local producer uses this same lock. Waiting here prevents reading a
# backup set while its database dump or COMPLETED marker is still changing.
exec 9>"${local_lock}"
flock -w 14400 9 || fail "timed out waiting for the local backup"

mapfile -t completed_sets < <(
  find "${backup_root}" -mindepth 2 -maxdepth 2 -type f -name COMPLETED \
    -printf '%h\n' | sort
)
(( ${#completed_sets[@]} > 0 )) || fail "no COMPLETED backup set found"
readonly backup_set="${completed_sets[-1]}"
[[ -f "${backup_set}/SHA256SUMS" ]] || \
  fail "completed set has no SHA256SUMS: ${backup_set}"
if [[ "${dataset}" == aiops ]]; then
  command -v python3 >/dev/null || fail "missing command: python3"
  [[ -f "${backup_set}/backup-set-manifest.json" ]] || \
    fail "AIOps backup set has no backup-set-manifest.json: ${backup_set}"
readonly backup_set_id="$(python3 - "${backup_set}/backup-set-manifest.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as manifest:
    print(json.load(manifest)["backup_set_id"])
PY
)"
[[ "${backup_set_id}" =~ ^[0-9]{8}T[0-9]{6}-[0-9]{4}$ ]] || \
  fail "invalid backup_set_id: ${backup_set_id}"
[[ "${backup_set_id}" == "$(basename "${backup_set}")" ]] || \
  fail "manifest backup_set_id does not match local set directory"
grep -Fq -- './backup-set-manifest.json' "${backup_set}/SHA256SUMS" || \
  fail "backup_set_id manifest is absent from SHA256SUMS"
  readonly set_tag="ness-backup-set-${backup_set_id}"
else
  readonly backup_set_id="$(basename "${backup_set}")"
fi

if [[ "${dataset}" == aiops ]]; then
  (cd "${backup_set}" && sha256sum -c SHA256SUMS)
else
  sha256sum -c "${backup_set}/SHA256SUMS"
fi

# A repository is initialized deliberately with the 'init' action. Any other
# repository/authentication/network failure stops the scheduled copy closed.
restic --retry-lock 30m cat config >/dev/null

(
  cd "${backup_set}"
  if [[ "${dataset}" == aiops ]]; then
    restic --retry-lock 30m backup \
      --host "${NESS_BACKUP_HOST_ID}" \
      --tag "${snapshot_tag}" \
      --tag "${set_tag}" \
      .
  else
    restic --retry-lock 30m backup \
      --host "${NESS_BACKUP_HOST_ID}" \
      --tag "${snapshot_tag}" \
      --skip-if-unchanged \
      .
  fi
)

restic --retry-lock 30m check \
  --read-data-subset="${check_percent}%"

# keep_last cannot be zero. Restic also refuses to remove the final snapshot
# in a group, adding a second guard against retention deleting the last copy.
restic --retry-lock 30m forget \
  --host "${NESS_BACKUP_HOST_ID}" \
  --tag "${snapshot_tag}" \
  --group-by host,paths \
  --keep-last "${keep_last}" \
  --prune

restic --retry-lock 30m check
if [[ "${dataset}" == aiops ]]; then
  restic snapshots \
    --host "${NESS_BACKUP_HOST_ID}" \
    --tag "${snapshot_tag},${set_tag}" \
    --latest 1
  echo "Object-storage backup verified: dataset=${dataset} backup_set_id=${backup_set_id}"
else
  restic snapshots \
    --host "${NESS_BACKUP_HOST_ID}" \
    --tag "${snapshot_tag}" \
    --latest 1
  echo "Object-storage backup verified: dataset=${dataset} set=${backup_set_id}"
fi
