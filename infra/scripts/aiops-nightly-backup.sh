#!/usr/bin/env bash
set -euo pipefail

umask 077

backup_root="/opt/n-infraops/backups/nightly"
app_dir="/opt/n-infraops/app"
compose=(docker compose -f "${app_dir}/docker-compose.yml" -f "${app_dir}/docker-compose.tickets.yml")
stamp="$(date +%Y%m%dT%H%M%S%z)"
destination="${backup_root}/${stamp}"
lock_file="/run/lock/ness-aiops-backup.lock"

exec 9>"${lock_file}"
flock -n 9 || {
  echo "another AIOps backup is already running" >&2
  exit 1
}

install -d -o root -g root -m 700 "${backup_root}"

available_kib="$(df --output=avail "${backup_root%/nightly}" | tail -1 | tr -d ' ')"
if (( available_kib < 40 * 1024 * 1024 )); then
  echo "less than 40 GiB available for backup" >&2
  exit 1
fi

install -d -m 700 "${destination}/postgres" "${destination}/volumes"

"${compose[@]}" exec -T postgres sh -lc \
  'pg_dumpall --globals-only -U "$POSTGRES_USER"' \
  | gzip -9 > "${destination}/postgres/globals.sql.gz"

mapfile -t databases < <(
  "${compose[@]}" exec -T postgres sh -lc \
    'psql -At -U "$POSTGRES_USER" -d postgres -c "SELECT datname FROM pg_database WHERE datallowconn AND NOT datistemplate ORDER BY datname"'
)

for database in "${databases[@]}"; do
  "${compose[@]}" exec -T postgres sh -lc \
    'pg_dump -Fc -U "$POSTGRES_USER" "$1"' sh "${database}" \
    > "${destination}/postgres/${database}.dump"
done

"${compose[@]}" exec -T glpi-db sh -lc \
  'mariadb-dump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --events --all-databases' \
  | gzip -9 > "${destination}/glpi-all-databases.sql.gz"

tar -czf "${destination}/app-config.tar.gz" -C "${app_dir}" \
  .env Caddyfile docker-compose.yml docker-compose.tickets.yml

/usr/local/sbin/ness-aiops-deployment-backup "${destination}"

stopped_containers=()
restart_stopped_containers() {
  local container
  for container in "${stopped_containers[@]}"; do
    docker start "${container}" >/dev/null || true
  done
}
trap restart_stopped_containers EXIT

for container in ninf-n8n ninf-glpi; do
  if [[ "$(docker inspect --format '{{.State.Running}}' "${container}" 2>/dev/null || true)" == "true" ]]; then
    docker stop --time 30 "${container}" >/dev/null
    stopped_containers+=("${container}")
  fi
done

mapfile -t volumes < <(
  while read -r container_id; do
    docker inspect --format '{{range .Mounts}}{{if eq .Type "volume"}}{{println .Name}}{{end}}{{end}}' "${container_id}"
  done < <(cd "${app_dir}" && docker compose ps -aq; docker ps -aq --filter name='^/ninf-glpi$' --filter name='^/ninf-glpi-db$') \
    | sed '/^$/d' | sort -u
)

compose_api_id="$("${compose[@]}" ps -q api)"
[[ -n "${compose_api_id}" ]] || {
  echo 'could not resolve the running API container from Compose' >&2
  exit 1
}
compose_network="$(docker inspect --format \
  '{{range $name, $network := .NetworkSettings.Networks}}{{println $name}}{{end}}' \
  "${compose_api_id}" | sed -n '1p' | tr -d '\r')"
[[ -n "${compose_network}" ]] || {
  echo 'could not resolve the Compose project network' >&2
  exit 1
}
docker network inspect "${compose_network}" >/dev/null

for volume in "${volumes[@]}"; do
  case "${volume}" in
    app_pg-data|app_glpi-db-data)
      continue
      ;;
  esac
  safe_name="${volume//[^a-zA-Z0-9_.-]/_}"
  docker run --rm --network "${compose_network}" \
    -v "${volume}:/source:ro" \
    -v "${destination}/volumes:/backup" \
    caddy:2-alpine sh -c \
    "cd /source && tar -czf /backup/${safe_name}.tar.gz ."
done

restart_stopped_containers
stopped_containers=()
trap - EXIT

printf '{"backup_set_id":"%s"}\n' "${stamp}" > "${destination}/backup-set-manifest.json"
(
  cd "${destination}"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum
) > "${destination}/SHA256SUMS"

required_artifacts=(
  postgres/globals.sql.gz
  postgres/nessops.dump
  glpi-all-databases.sql.gz
  volumes/app_glpi-state.tar.gz
  app-config.tar.gz
  deployment-app.tar.gz
  deployment-runtime.tar.gz
  deployment-images.json
  deployment-local-images.tar.gz
  deployment-hub-database.tar.gz
  backup-set-manifest.json
)
for artifact in "${required_artifacts[@]}" SHA256SUMS; do
  [[ -s "${destination}/${artifact}" ]] || {
    echo "required backup artifact missing or empty: ${artifact}" >&2
    exit 1
  }
done
for artifact in "${required_artifacts[@]}"; do
  grep -Fq -- "./${artifact}" "${destination}/SHA256SUMS" || {
    echo "required backup artifact is absent from checksum manifest: ${artifact}" >&2
    exit 1
  }
done

gzip -t "${destination}/postgres/globals.sql.gz" "${destination}/glpi-all-databases.sql.gz"
for dump in "${destination}"/postgres/*.dump; do
  "${compose[@]}" exec -T postgres pg_restore -l < "${dump}" >/dev/null
done
for archive in "${destination}"/*.tar.gz "${destination}"/volumes/*.tar.gz; do
  tar -tzf "${archive}" >/dev/null
done
(cd "${destination}" && sha256sum -c SHA256SUMS)

chmod -R go-rwx "${destination}"
touch "${destination}/COMPLETED"
echo "AIOps backup completed: ${destination}"
