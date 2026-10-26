#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
exec 9>/run/lock/ness-aiops-restore-verify.lock
flock -n 9 || { echo 'another AIOps restore verification is running' >&2; exit 6; }

backup_root="/opt/n-infraops/backups/nightly"
backup_dir="${1:-}"
remote_restore=0
if [[ "${backup_dir}" == "--remote" ]]; then
  remote_restore=1
  backup_dir=""
elif [[ "${backup_dir}" == -* ]]; then
  echo "usage: $0 [--remote | completed-backup-directory]" >&2
  exit 2
fi

if [[ -z "${backup_dir}" ]]; then
  # An interrupted/new backup directory is not a recoverable set.
  backup_dir="$(find "${backup_root}" -mindepth 2 -maxdepth 2 -type f -name COMPLETED -printf '%h\n' | sort | tail -1)"
  [[ -n "${backup_dir}" ]] || { echo 'no completed backup available' >&2; exit 3; }
fi

backup_dir="$(realpath -e "${backup_dir}")"
case "${backup_dir}" in
  "${backup_root}"/*) ;;
  *)
    echo "backup must be below ${backup_root}" >&2
    exit 2
    ;;
esac

[[ -f "${backup_dir}/COMPLETED" ]] || {
  echo "backup is not marked COMPLETED: ${backup_dir}" >&2
  exit 3
}

run_id="$(date +%Y%m%dt%H%M%S)-$$"
started_at="$(date +%s)"
remote_dir=""
if (( remote_restore )); then
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
  env_file=/etc/ness-os/backup-s3.env
  test "$(stat -c '%u:%a' "${env_file}")" = '0:600'
  set -a
  . "${env_file}"
  set +a
  export RESTIC_REPOSITORY="s3:${CONTABO_S3_ENDPOINT%/}/${CONTABO_S3_BUCKET}/ness-os/${NESS_BACKUP_HOST_ID}/aiops"
  export RESTIC_CACHE_DIR=/var/cache/ness-os-restic
  remote_dir="/opt/n-infraops/restore-tests/remote-${run_id}"
  install -d -o root -g root -m 700 /opt/n-infraops/restore-tests
  install -d -o root -g root -m 700 "${remote_dir}"
  remote_snapshots="$(restic snapshots --json --host "${NESS_BACKUP_HOST_ID}")"
  printf '%s\n' "${remote_snapshots}" > "${remote_dir}/snapshots.json"
  remote_snapshot="$(python3 - "${backup_set_id}" "${remote_dir}/snapshots.json" <<'PY'
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
  restic restore "${remote_snapshot}" --target "${remote_dir}" --verify
  mapfile -t remote_markers < <(find "${remote_dir}" -type f -name COMPLETED)
  [[ ${#remote_markers[@]} -eq 1 ]] || { echo 'remote snapshot must contain one completed set' >&2; exit 4; }
  backup_dir="$(dirname "${remote_markers[0]}")"
  restored_set_id="$(python3 - "${backup_dir}/backup-set-manifest.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as manifest:
    print(json.load(manifest)["backup_set_id"])
PY
)"
  [[ "${restored_set_id}" == "${backup_set_id}" ]] || {
    echo 'restored backup_set_id does not match its snapshot tag' >&2; exit 4;
  }
fi
backup_set_id="${backup_set_id:-$(basename "${backup_dir}")}"
cd "${backup_dir}"
sha256sum -c SHA256SUMS >/dev/null

pg_admin="restore_${run_id//-/_}"
pg_container="ness-restore-pg-${run_id}"
db_container="ness-restore-mariadb-${run_id}"
pg_volume="ness_restore_pg_${run_id}"
db_volume="ness_restore_mariadb_${run_id}"
extract_dir="/opt/n-infraops/restore-tests/${run_id}"

for value in "${pg_container}" "${db_container}" "${pg_volume}" "${db_volume}"; do
  [[ "${value}" =~ ^ness[-_]restore[-_][a-z0-9_-]+$ ]] || {
    echo "unsafe generated resource name: ${value}" >&2
    exit 4
  }
done

cleanup() {
  docker rm -f "${pg_container}" "${db_container}" >/dev/null 2>&1 || true
  docker volume rm "${pg_volume}" "${db_volume}" >/dev/null 2>&1 || true
  rm -rf -- "${extract_dir}"
  [[ -z "${remote_dir}" ]] || rm -rf -- "${remote_dir}"
}
trap cleanup EXIT

diagnose_error() {
  echo "isolated restore failed; disposable container diagnostics follow" >&2
  docker logs --tail 80 "${pg_container}" 2>&1 || true
  docker logs --tail 80 "${db_container}" 2>&1 || true
}
trap diagnose_error ERR

install -d -o root -g root -m 700 "${extract_dir}"

pg_image="$(docker inspect --format '{{.Image}}' ninf-postgres)"
db_image="$(docker inspect --format '{{.Image}}' ninf-glpi-db)"

docker volume create "${pg_volume}" >/dev/null
docker run -d --name "${pg_container}" \
  --network none \
  -e POSTGRES_PASSWORD=restore-test-only \
  -e POSTGRES_USER="${pg_admin}" \
  -e POSTGRES_DB=restore_control \
  -v "${pg_volume}:/var/lib/postgresql/data" \
  "${pg_image}" >/dev/null

for _ in $(seq 1 120); do
  if docker logs "${pg_container}" 2>&1 | grep "PostgreSQL init process complete" >/dev/null \
    && docker exec "${pg_container}" pg_isready -U "${pg_admin}" -d restore_control >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker logs "${pg_container}" 2>&1 | grep "PostgreSQL init process complete" >/dev/null
docker exec "${pg_container}" pg_isready -U "${pg_admin}" -d restore_control >/dev/null

# Restore roles before objects, without suppressing SQL errors. The disposable
# administrator has a unique name, so production roles cannot collide with it.
zcat postgres/globals.sql.gz \
  | docker exec -i "${pg_container}" psql -X -v ON_ERROR_STOP=1 -U "${pg_admin}" -d restore_control >/dev/null
docker exec "${pg_container}" dropdb -U "${pg_admin}" postgres

pg_restored=0
for dump in postgres/*.dump; do
  database="$(basename "${dump}" .dump)"
  [[ "${database}" =~ ^[a-zA-Z0-9_-]+$ ]] || {
    echo "unsafe database name in backup: ${database}" >&2
    exit 5
  }
  docker exec -i "${pg_container}" pg_restore \
    --exit-on-error --create -U "${pg_admin}" -d restore_control < "${dump}" >/dev/null
  relation_count="$(docker exec "${pg_container}" psql -At -U "${pg_admin}" -d "${database}" \
    -c "SELECT count(*) FROM pg_class WHERE relkind IN ('r','p') AND relnamespace NOT IN (SELECT oid FROM pg_namespace WHERE nspname LIKE 'pg_%' OR nspname='information_schema')")"
  echo "postgres database=${database} relations=${relation_count}"
  docker exec "${pg_container}" psql -X -At -U "${pg_admin}" -d "${database}" \
    -c "SELECT 'postgres_owner=' || datname || ':' || pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()"
  pg_restored=$((pg_restored + 1))
done

role_count="$(docker exec "${pg_container}" psql -At -U "${pg_admin}" -d restore_control \
  -c "SELECT count(*) FROM pg_roles")"
echo "postgres_roles_restored=${role_count}"

docker volume create "${db_volume}" >/dev/null
docker run -d --name "${db_container}" \
  --network none \
  -e MARIADB_ROOT_PASSWORD=restore-test-only \
  -v "${db_volume}:/var/lib/mysql" \
  "${db_image}" >/dev/null

for _ in $(seq 1 120); do
  if docker logs "${db_container}" 2>&1 | grep "MariaDB init process done" >/dev/null \
    && docker exec "${db_container}" mariadb-admin -uroot -prestore-test-only ping >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker logs "${db_container}" 2>&1 | grep "MariaDB init process done" >/dev/null
docker exec "${db_container}" mariadb-admin -uroot -prestore-test-only ping >/dev/null

zcat glpi-all-databases.sql.gz \
  | docker exec -i "${db_container}" mariadb -uroot -prestore-test-only >/dev/null

glpi_tables="$(docker exec "${db_container}" mariadb -N -B -uroot -prestore-test-only \
  -e "SELECT count(*) FROM information_schema.tables WHERE table_schema='glpi'")"
glpi_projects="$(docker exec "${db_container}" mariadb -N -B -uroot -prestore-test-only \
  -e "SELECT count(*) FROM information_schema.tables WHERE table_schema='glpi' AND table_name IN ('glpi_projects','glpi_projecttasks')")"
echo "mariadb database=glpi tables=${glpi_tables} project_tables=${glpi_projects}"

archive_count=0
for archive in *.tar.gz volumes/*.tar.gz; do
  target="${extract_dir}/${archive_count}"
  install -d -m 700 "${target}"
  tar -xzf "${archive}" -C "${target}"
  archive_count=$((archive_count + 1))
done

echo "archives_restored=${archive_count}"
echo "postgres_databases_restored=${pg_restored}"
echo "restore_elapsed_seconds=$(( $(date +%s) - started_at ))"
echo "isolated_restore=PASS backup_set_id=${backup_set_id} remote=${remote_restore}"
