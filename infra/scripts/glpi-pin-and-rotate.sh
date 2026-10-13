#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

app_dir="/opt/n-infraops/app"
staged_compose="${1:-/tmp/docker-compose.tickets.pinned.yml}"
live_compose="${app_dir}/docker-compose.tickets.yml"
env_file="${app_dir}/.env"
stamp="$(date +%Y%m%dt%H%M%S%z)"
rollback_dir="/opt/n-infraops/change-backups/glpi-pin-${stamp}"
expected_glpi_digest="sha256:48ec3ce559fda9eaf73c6fe2f0fc2dd382ef013f2dda14004f34ee88ec17c8b8"

[[ -f "${staged_compose}" ]] || {
  echo "staged compose not found" >&2
  exit 2
}
[[ -f "${live_compose}" && -f "${env_file}" ]] || {
  echo "live compose or environment file not found" >&2
  exit 3
}

grep -Fq "elestio/glpi:latest@${expected_glpi_digest}" "${staged_compose}"
if grep -Eq 'NINF_GLPI_DB_(ROOT_)?PASSWORD:-' "${staged_compose}"; then
  echo "staged compose still contains password defaults" >&2
  exit 4
fi

running_glpi_image="$(docker inspect --format '{{.Image}}' ninf-glpi)"
[[ "${running_glpi_image}" == "${expected_glpi_digest}" ]] || {
  echo "running GLPI image does not match approved digest" >&2
  exit 5
}

# Both the candidate and rollback Compose must retain the exact running state
# volume. A credential rotation cannot safely repair an anonymous-volume drift.
preflight="$(dirname "${BASH_SOURCE[0]}")/glpi_state_volume_preflight.py"
python3 "${preflight}" --compose "${app_dir}/docker-compose.yml" --compose "${staged_compose}"
python3 "${preflight}" --compose "${app_dir}/docker-compose.yml" --compose "${live_compose}"

old_root="$(docker exec ninf-glpi-db sh -lc 'printf %s "$MYSQL_ROOT_PASSWORD"')"
old_db="$(docker exec ninf-glpi sh -lc 'printf %s "$DB_PASSWORD"')"
[[ -n "${old_root}" && -n "${old_db}" ]]

new_root="$(openssl rand -base64 48 | tr -d '\n')"
new_db="$(openssl rand -base64 48 | tr -d '\n')"

install -d -o root -g root -m 700 "${rollback_dir}"
install -o root -g root -m 600 "${live_compose}" "${rollback_dir}/docker-compose.tickets.yml"
install -o root -g root -m 600 "${env_file}" "${rollback_dir}/env"
docker cp ninf-glpi:/var/glpi/config/config_db.php "${rollback_dir}/config_db.php"
chmod 0600 "${rollback_dir}/config_db.php"

rollback_required=true
rollback() {
  local exit_code=$?
  trap - ERR
  if [[ "${rollback_required}" == "true" ]]; then
    echo "validation failed; rolling GLPI credentials and compose back" >&2
    docker exec -e RESTORE_ROOT="${old_root}" -e RESTORE_DB="${old_db}" \
      -e CURRENT_ROOT="${new_root}" ninf-glpi-db sh -lc '
        mariadb -uroot -p"$CURRENT_ROOT" --protocol=socket <<SQL
ALTER USER IF EXISTS '\''root'\''@'\''localhost'\'' IDENTIFIED BY '\''${RESTORE_ROOT}'\'';
ALTER USER IF EXISTS '\''root'\''@'\''%'\'' IDENTIFIED BY '\''${RESTORE_ROOT}'\'';
ALTER USER IF EXISTS '\''glpi'\''@'\''%'\'' IDENTIFIED BY '\''${RESTORE_DB}'\'';
FLUSH PRIVILEGES;
SQL
      ' >/dev/null 2>&1 || true
    install -o root -g root -m 600 "${rollback_dir}/env" "${env_file}"
    install -o root -g root -m 600 "${rollback_dir}/docker-compose.tickets.yml" "${live_compose}"
    docker cp "${rollback_dir}/config_db.php" ninf-glpi:/var/glpi/config/config_db.php >/dev/null 2>&1 || true
    cd "${app_dir}"
    docker compose -f docker-compose.yml -f docker-compose.tickets.yml up -d --force-recreate glpi-db glpi >/dev/null 2>&1 || true
  fi
  exit "${exit_code}"
}
trap rollback ERR

docker exec -e ROTATE_ROOT="${new_root}" -e ROTATE_DB="${new_db}" \
  ninf-glpi-db sh -lc '
    mariadb -uroot -p"$MYSQL_ROOT_PASSWORD" --protocol=socket <<SQL
ALTER USER IF EXISTS '\''root'\''@'\''localhost'\'' IDENTIFIED BY '\''${ROTATE_ROOT}'\'';
ALTER USER IF EXISTS '\''root'\''@'\''%'\'' IDENTIFIED BY '\''${ROTATE_ROOT}'\'';
ALTER USER IF EXISTS '\''glpi'\''@'\''%'\'' IDENTIFIED BY '\''${ROTATE_DB}'\'';
FLUSH PRIVILEGES;
SQL
  ' >/dev/null

env_tmp="$(mktemp "${app_dir}/.env.glpi.XXXXXX")"
grep -Ev '^NINF_GLPI_DB_(ROOT_)?PASSWORD=' "${env_file}" > "${env_tmp}"
printf 'NINF_GLPI_DB_ROOT_PASSWORD=%s\n' "${new_root}" >> "${env_tmp}"
printf 'NINF_GLPI_DB_PASSWORD=%s\n' "${new_db}" >> "${env_tmp}"
install -o root -g root -m 600 "${env_tmp}" "${env_file}"
rm -f -- "${env_tmp}"
install -o root -g root -m 600 "${staged_compose}" "${live_compose}"

# GLPI stores the database password in its persistent config volume. Keep it in
# lock-step with the database account before recreating either container.
export NEW_GLPI_DB_PASSWORD="${new_db}"
docker exec -e NEW_GLPI_DB_PASSWORD ninf-glpi php -r '
$path="/var/glpi/config/config_db.php";
$source=file_get_contents($path);
$escaped=str_replace(["\\\\", "\x27"], ["\\\\\\\\", "\\\\\x27"], getenv("NEW_GLPI_DB_PASSWORD"));
$updated=preg_replace_callback(
  "/(public[[:space:]]+\\\$dbpassword[[:space:]]*=[[:space:]]*)\x27[^\x27]*\x27;/",
  static fn($match) => $match[1]."\x27".$escaped."\x27;",
  $source,
  1,
  $count
);
if ($count !== 1 || file_put_contents($path,$updated) === false) {
  fwrite(STDERR,"persistent GLPI database config update failed\n");
  exit(1);
}
'
unset NEW_GLPI_DB_PASSWORD

cd "${app_dir}"
docker compose -f docker-compose.yml -f docker-compose.tickets.yml config -q
docker compose -f docker-compose.yml -f docker-compose.tickets.yml up -d --force-recreate glpi-db glpi >/dev/null

for _ in $(seq 1 90); do
  if docker exec ninf-glpi-db sh -lc 'mariadb-admin -uroot -p"$MYSQL_ROOT_PASSWORD" ping' >/dev/null 2>&1 \
    && docker exec ninf-glpi php /var/www/glpi/bin/console --version >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

docker exec ninf-glpi-db sh -lc 'mariadb-admin -uroot -p"$MYSQL_ROOT_PASSWORD" ping' >/dev/null
glpi_version="$(docker exec ninf-glpi php /var/www/glpi/bin/console --version)"
db_tables="$(docker exec ninf-glpi-db sh -lc 'mariadb -N -B -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "SELECT count(*) FROM information_schema.tables WHERE table_schema=DATABASE()"')"
http_status="$(curl -k -sS -o /dev/null -w '%{http_code}' --resolve n-ticket.ness.com.br:443:127.0.0.1 https://n-ticket.ness.com.br/)"
internal_http_status="$(docker exec ninf-glpi sh -lc 'curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1/')"

[[ "${db_tables}" =~ ^[0-9]+$ && "${db_tables}" -gt 0 ]]
[[ "${http_status}" =~ ^(200|302|303)$ ]]
[[ "${internal_http_status}" =~ ^(200|301|302|303)$ ]]

rollback_required=false
trap - ERR

echo "glpi_image_pinned=${expected_glpi_digest}"
echo "glpi_version=${glpi_version}"
echo "glpi_tables=${db_tables}"
echo "glpi_http_status=${http_status}"
echo "glpi_internal_http_status=${internal_http_status}"
echo "credentials_rotated=PASS"
echo "rollback_material=${rollback_dir}"
