#!/usr/bin/env bash
# Promote API + workers on the AIOps host to an immutable API image digest.
# Usage (on the host, as root): aiops-promote-hub-api.sh <commit-sha40> <api-ref@sha256> <staged-compose-dir>
# The staged dir holds docker-compose.yml and docker-compose.tickets.yml from <commit>.
# Frontend, databases, GLPI, Authentik and Caddy are never recreated.
set -Eeuo pipefail
umask 077

commit="${1:?commit sha required}"
api_ref="${2:?api image ref required}"
staged="${3:?staged compose dir required}"
[[ "${commit}" =~ ^[0-9a-f]{40}$ ]]
[[ "${api_ref}" =~ ^ghcr\.io/resper1965/ninf-api@sha256:[0-9a-f]{64}$ ]]
[[ -f "${staged}/docker-compose.yml" && -f "${staged}/docker-compose.tickets.yml" ]]

current_dir="$(docker inspect ninf-api --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}')"
target_dir="/opt/n-infraops/releases/${commit}/app"
[[ -f "${current_dir}/.env" ]]
[[ "${current_dir}" != "${target_dir}" ]]
[[ ! -e "${target_dir}" ]]
services=(api worker-alerts worker-ml)

# 1. Backup under 30 min old, verified by its COMPLETED marker. Reuse the
# nightly when fresh: the backup stops GLPI and n8n for several minutes.
while systemctl is-active -q ness-aiops-backup.service; do sleep 30; done
latest_backup() { find /opt/n-infraops/backups/nightly -mindepth 1 -maxdepth 1 -type d -printf "%T@ %f\n" | sort -rn | head -1 | cut -d" " -f2; }
backup_set="$(latest_backup)"
if ! find "/opt/n-infraops/backups/nightly/${backup_set}" -maxdepth 0 -mmin -30 | grep -q .; then
  systemctl start ness-aiops-backup.service
  backup_set="$(latest_backup)"
fi
[[ -f "/opt/n-infraops/backups/nightly/${backup_set}/COMPLETED" ]]
find "/opt/n-infraops/backups/nightly/${backup_set}" -maxdepth 0 -mmin -30 | grep -q .

# 2. Stage the new release next to the current one; the current stays as rollback.
install -d -m 0755 "$(dirname "${target_dir}")"
cp -a "${current_dir}" "${target_dir}"
install -m 0644 "${staged}/docker-compose.yml" "${staged}/docker-compose.tickets.yml" "${target_dir}/"
sed -i -E "s#^NINF_API_IMAGE=.*#NINF_API_IMAGE=${api_ref}#" "${target_dir}/.env"
compose_new=(docker compose -p app -f "${target_dir}/docker-compose.yml" -f "${target_dir}/docker-compose.tickets.yml")
compose_old=(docker compose -p app -f "${current_dir}/docker-compose.yml" -f "${current_dir}/docker-compose.tickets.yml")
"${compose_new[@]}" config -q
docker pull -q "${api_ref}" >/dev/null

evidence="/opt/n-infraops/releases/${commit}/evidence"
install -d -m 0700 "${evidence}"
docker ps --format '{{.Names}} {{.Image}}' | sort > "${evidence}/pre-promotion-images.txt"

# 3. Additive, idempotent migration and canary before touching live services.
"${compose_new[@]}" run --rm --no-deps -T api python -m app.migrate
canary=ninf-api-canary
"${compose_new[@]}" run -d --rm --no-deps --name "${canary}" api >/dev/null
trap 'docker rm -f "${canary}" >/dev/null 2>&1 || true' EXIT
ready=false
for _ in $(seq 1 30); do
  docker exec "${canary}" curl -fsS http://localhost:8000/ready >/dev/null 2>&1 && { ready=true; break; }
  sleep 2
done
[[ "${ready}" == true ]]
docker rm -f "${canary}" >/dev/null

# 4. Promote; any failure from here restores the previous release.
rollback() {
  code=$?
  trap - ERR
  echo 'promotion failed; restoring previous release' >&2
  "${compose_old[@]}" up -d --no-deps --force-recreate "${services[@]}" >/dev/null 2>&1 || true
  exit "${code}"
}
trap rollback ERR
"${compose_new[@]}" up -d --no-deps --force-recreate "${services[@]}"

for _ in $(seq 1 60); do
  states="$(for c in ninf-api ninf-worker-alerts ninf-worker-ml; do docker inspect -f '{{.State.Health.Status}}' "$c"; done | sort -u | tr '\n' ' ')"
  [[ "${states}" == "healthy " ]] && break
  sleep 5
done
[[ "${states}" == "healthy " ]]
docker exec ninf-api curl -fsS http://localhost:8000/ready >/dev/null
hub_status="$(curl -ksS -o /dev/null -w '%{http_code}' --resolve hub.ness.com.br:443:127.0.0.1 https://hub.ness.com.br/)"
[[ "${hub_status}" =~ ^(200|301|302|303)$ ]]
for c in ninf-api ninf-worker-alerts ninf-worker-ml; do
  [[ "$(docker inspect -f '{{.Config.Image}}' "$c")" == "${api_ref}" ]]
done
# /ready does not exercise ticket delivery (26/10: PASS here, every alert failing after).
# Watch real alert tasks; any unexpected failure rolls back.
sleep "${ALERT_WATCH_SECONDS:-300}"
alert_failures="$(docker logs --since "${ALERT_WATCH_SECONDS:-300}s" ninf-worker-alerts 2>&1 | grep -c 'process_alert_v1\[.*raised unexpected' || true)"
echo "alert_failures=${alert_failures}"
[[ "${alert_failures}" == 0 ]]
trap - ERR

docker ps --format '{{.Names}} {{.Image}}' | sort > "${evidence}/post-promotion-images.txt"
printf 'release=%s\nprevious=%s\nbackup_set=%s\napi_image=%s\npromotion=PASS\nhub_http=%s\n' \
  "${commit}" "${current_dir}" "${backup_set}" "${api_ref}" "${hub_status}" | tee "${evidence}/promotion-context.txt"
printf 'rollback: docker compose -p app -f %s/docker-compose.yml -f %s/docker-compose.tickets.yml up -d --no-deps --force-recreate %s\n' \
  "${current_dir}" "${current_dir}" "${services[*]}"
