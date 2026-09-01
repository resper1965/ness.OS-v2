#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
app_dir=/opt/n-infraops/app
live_compose="${app_dir}/docker-compose.yml"
staged_compose="${1:-/tmp/docker-compose.pinned.yml}"
stamp="$(date +%Y%m%dt%H%M%S%z)"
rollback_dir="/opt/n-infraops/change-backups/aiops-image-pin-${stamp}"

[[ -f "${staged_compose}" && -f "${live_compose}" ]]
for image in timescale/timescaledb redis evoapicloud/evolution-api \
  evoapicloud/evolution-manager caddy docker.n8n.io/n8nio/n8n \
  ghcr.io/goauthentik/server; do
  grep -Eq "image:[[:space:]]+${image}:[^[:space:]]+@sha256:[0-9a-f]{64}" "${staged_compose}"
done

install -d -o root -g root -m 0700 "${rollback_dir}"
install -o root -g root -m 0600 "${live_compose}" "${rollback_dir}/docker-compose.yml"

rollback_required=true
rollback() {
  exit_code=$?
  trap - ERR
  if [[ "${rollback_required}" == true ]]; then
    echo 'validation failed; restoring previous AIOps compose' >&2
    install -o root -g root -m 0600 "${rollback_dir}/docker-compose.yml" "${live_compose}"
    cd "${app_dir}"
    docker compose -f docker-compose.yml -f docker-compose.tickets.yml up -d >/dev/null 2>&1 || true
  fi
  exit "${exit_code}"
}
trap rollback ERR

install -o root -g root -m 0600 "${staged_compose}" "${live_compose}"
cd "${app_dir}"
docker compose -f docker-compose.yml -f docker-compose.tickets.yml config -q

services=(postgres redis evolution-api evolution-manager caddy n8n authentik-server authentik-worker)
docker compose -f docker-compose.yml -f docker-compose.tickets.yml pull "${services[@]}"

docker compose -f docker-compose.yml -f docker-compose.tickets.yml up -d --force-recreate postgres redis
for _ in $(seq 1 60); do
  postgres_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' ninf-postgres)"
  redis_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' ninf-redis)"
  [[ "${postgres_health}" == healthy && "${redis_health}" == healthy ]] && break
  sleep 2
done
[[ "${postgres_health}" == healthy && "${redis_health}" == healthy ]]

docker compose -f docker-compose.yml -f docker-compose.tickets.yml up -d --force-recreate \
  authentik-server authentik-worker evolution-api evolution-manager n8n
docker compose -f docker-compose.yml -f docker-compose.tickets.yml up -d --force-recreate caddy

for _ in $(seq 1 90); do
  running="$(docker ps --format '{{.Names}}' | wc -l)"
  unhealthy="$(docker ps --filter health=unhealthy --format '{{.Names}}' | wc -l)"
  starting="$(docker ps --filter health=starting --format '{{.Names}}' | wc -l)"
  [[ "${running}" -eq 14 && "${unhealthy}" -eq 0 && "${starting}" -eq 0 ]] && break
  sleep 2
done
[[ "${running}" -eq 14 && "${unhealthy}" -eq 0 && "${starting}" -eq 0 ]]

for container in ninf-postgres ninf-redis ninf-evolution ninf-evolution-manager \
  ninf-caddy ninf-n8n ninf-authentik-server ninf-authentik-worker; do
  image_ref="$(docker inspect -f '{{.Config.Image}}' "${container}")"
  [[ "${image_ref}" =~ @sha256:[0-9a-f]{64}$ ]]
done

glpi_status="$(docker exec ninf-glpi sh -lc 'curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1/')"
hub_status="$(curl -ksS -o /dev/null -w '%{http_code}' --resolve hub.ness.com.br:443:127.0.0.1 https://hub.ness.com.br/)"
sso_status="$(curl -ksS -o /dev/null -w '%{http_code}' --resolve sso.ness.com.br:443:127.0.0.1 https://sso.ness.com.br/)"
[[ "${glpi_status}" =~ ^(200|301|302|303)$ ]]
[[ "${hub_status}" =~ ^(200|301|302|303)$ ]]
[[ "${sso_status}" =~ ^(200|301|302|303)$ ]]

rollback_required=false
trap - ERR
printf 'pinned_services=%s\n' "${#services[@]}"
printf 'running_containers=%s\n' "${running}"
printf 'glpi_http=%s\n' "${glpi_status}"
printf 'hub_http=%s\n' "${hub_status}"
printf 'sso_http=%s\n' "${sso_status}"
printf 'image_pin=PASS\n'
printf 'rollback_material=%s\n' "${rollback_dir}"
