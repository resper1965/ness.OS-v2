#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

backup_root=/opt/n-infraops/backups/nightly
env_file=/etc/ness-os/backup-s3.env
backup_dir="${1:-}"
if [[ -z "${backup_dir}" ]]; then
  backup_dir="$(find "${backup_root}" -mindepth 2 -maxdepth 2 -type f -name COMPLETED \
    -printf '%h\n' | sort | tail -1)"
fi
[[ -n "${backup_dir}" ]] || { echo 'no completed local backup set' >&2; exit 3; }
backup_dir="$(realpath -e "${backup_dir}")"
case "${backup_dir}" in "${backup_root}"/*) ;; *) echo 'backup set is outside nightly root' >&2; exit 2 ;; esac
[[ -f "${backup_dir}/COMPLETED" && -f "${backup_dir}/SHA256SUMS" ]] || {
  echo 'local backup set is incomplete' >&2; exit 3;
}
backup_set_id="$(python3 - "${backup_dir}/backup-set-manifest.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as manifest:
    print(json.load(manifest)["backup_set_id"])
PY
)"
[[ "${backup_set_id}" =~ ^[0-9]{8}T[0-9]{6}-[0-9]{4}$ ]] || {
  echo 'invalid backup_set_id' >&2; exit 3;
}
[[ "${backup_set_id}" == "$(basename "${backup_dir}")" ]] || {
  echo 'manifest backup_set_id does not match local directory' >&2; exit 3;
}
grep -Fq -- './backup-set-manifest.json' "${backup_dir}/SHA256SUMS" || {
  echo 'backup_set_id manifest is not checksummed' >&2; exit 3;
}
(cd "${backup_dir}" && sha256sum -c SHA256SUMS >/dev/null)

test "$(stat -c '%u:%a' "${env_file}")" = '0:600'
exec 8>/run/lock/ness-object-storage-restic.lock
flock -n 8 || { echo 'object storage operation already running' >&2; exit 3; }
set -a
. "${env_file}"
set +a
export RESTIC_REPOSITORY="s3:${CONTABO_S3_ENDPOINT%/}/${CONTABO_S3_BUCKET}/ness-os/${NESS_BACKUP_HOST_ID}/aiops"
export RESTIC_CACHE_DIR=/var/cache/ness-os-restic
tag="ness-backup-set-${backup_set_id}"
install -d -o root -g root -m 700 /opt/n-infraops/restore-tests
work="$(mktemp -d /opt/n-infraops/restore-tests/remote-verify-XXXXXXXX)"
trap 'rm -rf -- "${work}"' EXIT

snapshots="$(restic snapshots --json --host "${NESS_BACKUP_HOST_ID}")"
printf '%s\n' "${snapshots}" > "${work}/snapshots.json"
snapshot="$(python3 - "${backup_set_id}" "${work}/snapshots.json" <<'PY'
import json, sys
set_id, snapshot_file = sys.argv[1:]
with open(snapshot_file, encoding="utf-8") as source:
    rows = json.load(source)
ids = [
    row["id"] for row in rows
    if "ness-dataset-aiops" in row.get("tags", [])
    and f"ness-backup-set-{set_id}" in row.get("tags", [])
]
assert len(ids) == 1, f"expected one snapshot for backup_set_id={set_id}, found {len(ids)}"
print(ids[0])
PY
)"
restic restore "${snapshot}" --target "${work}/restored" --verify
mapfile -t sums < <(find "${work}/restored" -type f -name SHA256SUMS)
[[ ${#sums[@]} -eq 1 ]] || { echo 'remote snapshot does not contain one checksum manifest' >&2; exit 4; }
restored_dir="$(dirname "${sums[0]}")"
(cd "${restored_dir}" && sha256sum -c SHA256SUMS >/dev/null)
[[ -f "${restored_dir}/COMPLETED" ]] || { echo 'remote set lacks COMPLETED marker' >&2; exit 4; }
restored_set_id="$(python3 - "${restored_dir}/backup-set-manifest.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as manifest:
    print(json.load(manifest)["backup_set_id"])
PY
)"
[[ "${restored_set_id}" == "${backup_set_id}" ]] || {
  echo 'restored manifest backup_set_id differs from its snapshot tag' >&2; exit 4;
}
echo "deployment_remote_restore=PASS backup_set_id=${backup_set_id} snapshot=${snapshot}"
