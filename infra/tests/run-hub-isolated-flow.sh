#!/usr/bin/env bash
# Disposable loopback-only flow test; no production secrets or published ports.
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly api_image="${NINF_TEST_API_IMAGE:?set a verified API image digest}"
[[ ${api_image} == *@sha256:* ]] || { echo 'API image digest is required' >&2; exit 2; }
readonly prefix="ness-isolated-flow-$$"
readonly pg="${prefix}-pg" redis="${prefix}-redis" runner="${prefix}-test"
cleanup() {
  docker rm -fv "${runner}" "${redis}" "${pg}" >/dev/null 2>&1 || true
  docker network rm "${prefix}" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create --internal "${prefix}" >/dev/null
docker run -d --name "${pg}" --network "${prefix}" --memory 1g --cpus 1 \
  -e POSTGRES_DB=nessops -e POSTGRES_USER=nessops \
  -e POSTGRES_PASSWORD=isolated-test-only \
  timescale/timescaledb:latest-pg16@sha256:ba149561ad4ddff5940d6eb0a0df60aefd1355cee1a450928f271267038fc888 >/dev/null
docker run -d --name "${redis}" --network "container:${pg}" --memory 128m --cpus 0.5 \
  redis:7-alpine@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99 >/dev/null
ready=0
for ((attempt=0; attempt<60; attempt++)); do
  if docker exec "${pg}" pg_isready -h 127.0.0.1 -U nessops >/dev/null 2>&1 &&
    [[ "$(docker exec "${redis}" redis-cli ping 2>/dev/null)" == PONG ]]; then
    ready=1; break
  fi
  sleep 1
done
[[ ${ready} == 1 ]] || { echo 'isolated dependencies not ready' >&2; exit 1; }
docker cp "${repo_root}/app/backend/sql/." "${pg}:/tmp/sql"
for script in 000_init.sql 001_schema.sql 002_push_subscriptions.sql 003_glpi_ticket_post_reservations.sql; do
  docker exec "${pg}" psql -v ON_ERROR_STOP=1 -U nessops -d nessops \
    -f "/tmp/sql/${script}" >/dev/null
done
docker run --rm --name "${runner}" --network "container:${pg}" \
  --memory 1g --cpus 1 --security-opt no-new-privileges:true \
  --mount "type=bind,src=${repo_root}/app,dst=/work,readonly" \
  --workdir /work/backend --entrypoint python \
  -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/work/backend:/work \
  -e NINF_LOCAL_FLOW_TEST=1 -e NINF_ALERT_NOTIFICATIONS_ENABLED=false \
  -e NINF_DATABASE_URL=postgresql+asyncpg://nessops:isolated-test-only@127.0.0.1:5432/nessops \
  -e NINF_REDIS_URL=redis://127.0.0.1:6379/0 \
  -e NINF_CELERY_BROKER_URL=redis://127.0.0.1:6379/1 \
  -e NINF_LLM_API_KEY= "${api_image}" \
  -m pytest -q -p no:cacheprovider --tb=short tests/test_hub_local_flow.py
