#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }
readonly backup_root=/var/backups/zabbix/nightly
readonly env_file=/etc/ness-os/backup-s3.env
readonly restore_root=/var/lib/ness-os/restic-restore-verify
readonly validator=/usr/local/sbin/ness-zabbix-isolated-restore-test

[[ -f "${env_file}" && ! -L "${env_file}" ]] || {
  echo 'Restic EnvironmentFile must be regular and non-symlink' >&2; exit 1;
}
[[ "$(stat -c '%u:%a' "${env_file}")" == '0:600' ]] || {
  echo 'Restic EnvironmentFile must be root-owned mode 0600' >&2; exit 1;
}
[[ -x "${validator}" ]] || { echo 'Zabbix restore validator is not installed' >&2; exit 1; }

exec 8>/run/lock/ness-zabbix-restic-restore.lock
flock -n 8 || { echo 'another Zabbix remote restore is running' >&2; exit 3; }

mapfile -t completed_sets < <(
  find "${backup_root}" -mindepth 2 -maxdepth 2 -type f -name COMPLETED \
    -printf '%h\n' | sort
)
(( ${#completed_sets[@]} > 0 )) || { echo 'no completed Zabbix backup set' >&2; exit 3; }
readonly backup_set="${completed_sets[-1]}"
"${validator}" --validate-set "${backup_set}" >/dev/null
readonly backup_set_id="$(python3 - "${backup_set}/backup-set-manifest.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as source:
    print(json.load(source)["backup_set_id"])
PY
)"

set -a
. "${env_file}"
set +a
export RESTIC_REPOSITORY="s3:${CONTABO_S3_ENDPOINT%/}/${CONTABO_S3_BUCKET}/ness-os/${NESS_BACKUP_HOST_ID}/zabbix"
export RESTIC_CACHE_DIR=/var/cache/ness-os-restic
install -d -o root -g root -m 700 "${restore_root}"
work="$(mktemp -d "${restore_root}/run-XXXXXXXX")"
trap 'rm -rf -- "${work}"' EXIT

restic_snapshots="$(restic snapshots --json --host "${NESS_BACKUP_HOST_ID}")"
printf '%s\n' "${restic_snapshots}" >"${work}/snapshots.json"
snapshot="$(python3 - "${backup_set_id}" "${work}/snapshots.json" <<'PY'
import json, sys
set_id, path = sys.argv[1:]
with open(path, encoding="utf-8") as source:
    rows = json.load(source)
ids = [
    row["id"] for row in rows
    if "ness-dataset-zabbix" in row.get("tags", [])
    and f"ness-backup-set-{set_id}" in row.get("tags", [])
]
assert len(ids) == 1, f"expected one Zabbix snapshot for backup_set_id={set_id}, found {len(ids)}"
print(ids[0])
PY
)"
restic restore "${snapshot}" --target "${work}/restored" --verify
mapfile -t markers < <(find "${work}/restored" -type f -name COMPLETED)
[[ ${#markers[@]} -eq 1 ]] || { echo 'snapshot must contain one completed backup set' >&2; exit 4; }
restored_set="$(dirname "${markers[0]}")"
restored_id="$(python3 - "${restored_set}/backup-set-manifest.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as source:
    print(json.load(source)["backup_set_id"])
PY
)"
[[ "${restored_id}" == "${backup_set_id}" ]] || {
  echo 'restored backup_set_id differs from the local set' >&2; exit 4;
}
"${validator}" "${restored_set}"
echo "external_restore=PASS backup_set_id=${backup_set_id} snapshot=${snapshot}"
