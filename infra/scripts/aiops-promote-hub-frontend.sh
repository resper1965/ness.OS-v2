#!/usr/bin/env bash
# Promote only the frontend on the AIOps host to an immutable image digest.
# Usage (on the host, as root): aiops-promote-hub-frontend.sh <frontend-ref@sha256> [--dry-run]
# The compose that counts is the one in the CURRENT release dir (the API promotion moves it),
# so this reads it from the running ninf-api, never from /opt/n-infraops/app.
# API, workers, databases, GLPI, Authentik and Caddy are never recreated.
set -Eeuo pipefail
umask 077

ref="${1:?frontend image ref required}"
dry="${2:-}"
[[ "${ref}" =~ ^ghcr\.io/resper1965/ninf-frontend@sha256:[0-9a-f]{64}$ ]]
[[ -z "${dry}" || "${dry}" == "--dry-run" ]]

dir="$(docker inspect ninf-api --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}')"
[[ -f "${dir}/.env" && -f "${dir}/docker-compose.yml" ]]
stamp="$(date +%Y%m%dT%H%M%S)"
dirs=("${dir}")
[[ -f /opt/n-infraops/app/.env && "${dir}" != /opt/n-infraops/app ]] && dirs+=(/opt/n-infraops/app)
compose=(docker compose -p app -f "${dir}/docker-compose.yml" -f "${dir}/docker-compose.tickets.yml")

echo "release_dir=${dir}"
echo "frontend_antes=$(docker inspect ninf-frontend --format '{{.Config.Image}}')"
if [[ "${dry}" == "--dry-run" ]]; then
  printf 'passos: backup .env em %s; trocar NINF_FRONTEND_IMAGE; pull; recriar so o frontend; conferir imagem e HTTP\n' "${dirs[*]}"
  exit 0
fi

# 1. Back up every .env we touch; a failure from here restores them and recreates the old image.
for d in "${dirs[@]}"; do cp -p "${d}/.env" "${d}/.env.bak-fe-${stamp}"; done
restore() {
  for d in "${dirs[@]}"; do cp -p "${d}/.env.bak-fe-${stamp}" "${d}/.env"; done
  "${compose[@]}" up -d --no-deps frontend >/dev/null 2>&1 || true
  echo "rollback: frontend restaurado de .env.bak-fe-${stamp}" >&2
}
trap restore ERR
trap 'restore; exit 1' INT TERM HUP  # sinal no meio da troca também volta atrás

# 2. Swap the image reference (add the line when the env never had it).
for d in "${dirs[@]}"; do
  if grep -q '^NINF_FRONTEND_IMAGE=' "${d}/.env"; then
    sed -i -E "s#^NINF_FRONTEND_IMAGE=.*#NINF_FRONTEND_IMAGE=${ref}#" "${d}/.env"
  else
    echo "NINF_FRONTEND_IMAGE=${ref}" >> "${d}/.env"
  fi
done

# 3. Recreate only the frontend and prove it runs the new image and answers.
docker pull -q "${ref}" >/dev/null
"${compose[@]}" up -d --no-deps frontend
sleep 8
[[ "$(docker inspect ninf-frontend --format '{{.Config.Image}}')" == "${ref}" ]]
docker exec ninf-caddy wget -q --spider http://ninf-frontend:3000/
code="$(curl -ksS -o /dev/null -m 15 -w '%{http_code}' --resolve hub.ness.com.br:443:127.0.0.1 https://hub.ness.com.br/)"
[[ "${code}" == 200 ]]
trap - ERR INT TERM HUP
echo "frontend_image=${ref}"
echo "hub_http=${code}"
