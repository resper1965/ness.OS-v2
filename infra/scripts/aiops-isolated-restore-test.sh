#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

backup_root="/opt/n-infraops/backups/nightly"
backup_dir="${1:-}"

if [[ -z "${backup_dir}" ]]; then
  backup_dir="$(find "${backup_root}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -r | head -1)"
  backup_dir="${backup_root}/${backup_dir}"
fi

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

cd "${backup_dir}"
sha256sum -c SHA256SUMS >/dev/null

run_id="$(date +%Y%m%dt%H%M%S)-$$"
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
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=postgres \
  -v "${pg_volume}:/var/lib/postgresql/data" \
  "${pg_image}" >/dev/null

for _ in $(seq 1 120); do
  if docker logs "${pg_container}" 2>&1 | grep -q "PostgreSQL init process complete" \
    && docker exec "${pg_container}" pg_isready -U postgres -d postgres >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker logs "${pg_container}" 2>&1 | grep -q "PostgreSQL init process complete"
docker exec "${pg_container}" pg_isready -U postgres -d postgres >/dev/null

pg_restored=0
for dump in postgres/*.dump; do
  database="$(basename "${dump}" .dump)"
  [[ "${database}" =~ ^[a-zA-Z0-9_-]+$ ]] || {
    echo "unsafe database name in backup: ${database}" >&2
    exit 5
  }
  if [[ "${database}" != "postgres" ]]; then
    docker exec "${pg_container}" createdb -U postgres "${database}"
  fi
  docker exec -i "${pg_container}" pg_restore \
    --exit-on-error --no-owner -U postgres -d "${database}" < "${dump}" >/dev/null
  relation_count="$(docker exec "${pg_container}" psql -At -U postgres -d "${database}" \
    -c "SELECT count(*) FROM pg_class WHERE relkind IN ('r','p') AND relnamespace NOT IN (SELECT oid FROM pg_namespace WHERE nspname LIKE 'pg_%' OR nspname='information_schema')")"
  echo "postgres database=${database} relations=${relation_count}"
  pg_restored=$((pg_restored + 1))
done

# The globals dump may change the disposable administrative role. Restore it
# only after all database validation, then verify that it produced roles.
zcat postgres/globals.sql.gz \
  | docker exec -i "${pg_container}" psql -v ON_ERROR_STOP=0 -U postgres -d postgres >/dev/null 2>&1 || true
role_count="$(docker exec "${pg_container}" psql -At -U postgres -d postgres \
  -c "SELECT count(*) FROM pg_roles")"
echo "postgres_roles_restored=${role_count}"

docker volume create "${db_volume}" >/dev/null
docker run -d --name "${db_container}" \
  --network none \
  -e MARIADB_ROOT_PASSWORD=restore-test-only \
  -v "${db_volume}:/var/lib/mysql" \
  "${db_image}" >/dev/null

for _ in $(seq 1 120); do
  if docker logs "${db_container}" 2>&1 | grep -q "MariaDB init process done" \
    && docker exec "${db_container}" mariadb-admin -uroot -prestore-test-only ping >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker logs "${db_container}" 2>&1 | grep -q "MariaDB init process done"
docker exec "${db_container}" mariadb-admin -uroot -prestore-test-only ping >/dev/null

zcat glpi-all-databases.sql.gz \
  | docker exec -i "${db_container}" mariadb -uroot -prestore-test-only >/dev/null

glpi_tables="$(docker exec "${db_container}" mariadb -N -B -uroot -prestore-test-only \
  -e "SELECT count(*) FROM information_schema.tables WHERE table_schema='glpi'")"
glpi_projects="$(docker exec "${db_container}" mariadb -N -B -uroot -prestore-test-only \
  -e "SELECT count(*) FROM information_schema.tables WHERE table_schema='glpi' AND table_name IN ('glpi_projects','glpi_projecttasks')")"
echo "mariadb database=glpi tables=${glpi_tables} project_tables=${glpi_projects}"

archive_count=0
for archive in app-config.tar.gz volumes/*.tar.gz; do
  target="${extract_dir}/${archive_count}"
  install -d -m 700 "${target}"
  tar -xzf "${archive}" -C "${target}"
  archive_count=$((archive_count + 1))
done

echo "archives_restored=${archive_count}"
echo "postgres_databases_restored=${pg_restored}"
echo "isolated_restore=PASS backup=${backup_dir}"
