#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
app_dir=/opt/n-infraops/app
env_file="${app_dir}/.env"
live_compose="${app_dir}/docker-compose.yml"
staged_compose="${1:-/tmp/docker-compose.hardened.yml}"
stamp="$(date +%Y%m%dt%H%M%S%z)"
rollback_dir="/opt/n-infraops/change-backups/aiops-secret-rotation-${stamp}"

[[ -f "${env_file}" && -f "${live_compose}" && -f "${staged_compose}" ]]
grep -Fq 'NINF_DB_PASSWORD:?NINF_DB_PASSWORD is required' "${staged_compose}"
grep -Fq 'NINF_AUTHENTIK_SECRET_KEY:?NINF_AUTHENTIK_SECRET_KEY is required' "${staged_compose}"

old_db_password="$(docker exec ninf-postgres sh -lc 'printf "%s" "$POSTGRES_PASSWORD"')"
old_authentik_secret="$(docker exec ninf-authentik-server sh -lc 'printf "%s" "$AUTHENTIK_SECRET_KEY"')"
[[ -n "${old_db_password}" && -n "${old_authentik_secret}" ]]

new_db_password="$(openssl rand -hex 32)"
new_authentik_secret="$(openssl rand -hex 48)"

install -d -o root -g root -m 0700 "${rollback_dir}"
install -o root -g root -m 0600 "${env_file}" "${rollback_dir}/env"
install -o root -g root -m 0600 "${live_compose}" "${rollback_dir}/docker-compose.yml"

rollback_required=true
rollback() {
  exit_code=$?
  trap - ERR
  if [[ "${rollback_required}" == true ]]; then
    echo 'validation failed; rolling AIOps secrets and configuration back' >&2
    docker exec -e ROLE_PASSWORD="${old_db_password}" ninf-postgres sh -lc \
      'psql -U nessops -d postgres -v ON_ERROR_STOP=1 <<SQL
ALTER ROLE nessops PASSWORD '\''${ROLE_PASSWORD}'\'';
SQL' \
      >/dev/null 2>&1 || true
    install -o root -g root -m 0600 "${rollback_dir}/env" "${env_file}"
    install -o root -g root -m 0600 "${rollback_dir}/docker-compose.yml" "${live_compose}"
    cd "${app_dir}"
    docker compose -f docker-compose.yml -f docker-compose.tickets.yml up -d --force-recreate \
      postgres api worker-alerts worker-ml evolution-api authentik-server authentik-worker >/dev/null 2>&1 || true
  fi
  exit "${exit_code}"
}
trap rollback ERR

docker exec -e ROLE_PASSWORD="${new_db_password}" ninf-postgres sh -lc \
  'psql -U nessops -d postgres -v ON_ERROR_STOP=1 <<SQL
ALTER ROLE nessops PASSWORD '\''${ROLE_PASSWORD}'\'';
SQL' \
  >/dev/null

env_tmp="$(mktemp "${app_dir}/.env.rotation.XXXXXX")"
grep -Ev '^(NINF_DB_PASSWORD|NINF_AUTHENTIK_SECRET_KEY|NINF_DATABASE_URL)=' "${env_file}" > "${env_tmp}"
printf 'NINF_DB_PASSWORD=%s\n' "${new_db_password}" >> "${env_tmp}"
printf 'NINF_AUTHENTIK_SECRET_KEY=%s\n' "${new_authentik_secret}" >> "${env_tmp}"
printf 'NINF_DATABASE_URL=postgresql+asyncpg://nessops:%s@postgres:5432/nessops\n' "${new_db_password}" >> "${env_tmp}"
install -o root -g root -m 0600 "${env_tmp}" "${env_file}"
rm -f -- "${env_tmp}"
install -o root -g root -m 0600 "${staged_compose}" "${live_compose}"

cd "${app_dir}"
docker compose -f docker-compose.yml -f docker-compose.tickets.yml config -q
docker compose -f docker-compose.yml -f docker-compose.tickets.yml up -d --force-recreate postgres
for _ in $(seq 1 60); do
  postgres_health="$(docker inspect -f '{{.State.Health.Status}}' ninf-postgres)"
  [[ "${postgres_health}" == healthy ]] && break
  sleep 2
done
[[ "${postgres_health}" == healthy ]]

docker compose -f docker-compose.yml -f docker-compose.tickets.yml up -d --force-recreate \
  api worker-alerts worker-ml evolution-api authentik-server authentik-worker

for _ in $(seq 1 90); do
  running="$(docker ps --format '{{.Names}}' | wc -l)"
  unhealthy="$(docker ps --filter health=unhealthy --format '{{.Names}}' | wc -l)"
  starting="$(docker ps --filter health=starting --format '{{.Names}}' | wc -l)"
  [[ "${running}" -eq 14 && "${unhealthy}" -eq 0 && "${starting}" -eq 0 ]] && break
  sleep 2
done
[[ "${running}" -eq 14 && "${unhealthy}" -eq 0 && "${starting}" -eq 0 ]]

docker exec ninf-api sh -lc 'python - <<"PY"
import asyncio
import asyncpg
import os
from urllib.parse import urlsplit

url = os.environ["NINF_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
async def check():
    connection = await asyncpg.connect(url)
    try:
        assert await connection.fetchval("select 1") == 1
    finally:
        await connection.close()
asyncio.run(check())
PY'

hub_status="$(curl -ksS -o /dev/null -w '%{http_code}' --resolve hub.ness.com.br:443:127.0.0.1 https://hub.ness.com.br/)"
sso_status="$(curl -ksS -o /dev/null -w '%{http_code}' --resolve sso.ness.com.br:443:127.0.0.1 https://sso.ness.com.br/)"
[[ "${hub_status}" =~ ^(200|301|302|303)$ ]]
[[ "${sso_status}" =~ ^(200|301|302|303)$ ]]

report="$(/usr/local/sbin/ness-aiops-secret-consumer-report)"
grep -Fqx 'shared_database_password_consistent=yes' <<<"${report}"
grep -Fqx 'database_password_uses_known_default=no' <<<"${report}"
grep -Fqx 'authentik_secret_uses_compose_default=no' <<<"${report}"

rollback_required=false
trap - ERR
printf 'postgres_password_rotated=PASS\n'
printf 'authentik_secret_rotated=PASS\n'
printf 'running_containers=%s\n' "${running}"
printf 'hub_http=%s\n' "${hub_status}"
printf 'sso_http=%s\n' "${sso_status}"
printf 'rollback_material=%s\n' "${rollback_dir}"
