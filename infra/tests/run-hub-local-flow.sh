#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
pg_name="ness-ci-flow-pg-$$"
redis_name="ness-ci-flow-redis-$$"
trap 'docker rm -f "$pg_name" "$redis_name" >/dev/null 2>&1 || true' EXIT

docker run -d --name "$pg_name" \
  -p 127.0.0.1:42561:5432 \
  -e POSTGRES_DB=nessops -e POSTGRES_USER=nessops \
  -e POSTGRES_PASSWORD=local-flow-only \
  timescale/timescaledb:latest-pg16@sha256:ba149561ad4ddff5940d6eb0a0df60aefd1355cee1a450928f271267038fc888 >/dev/null
docker run -d --name "$redis_name" \
  -p 127.0.0.1:42562:6379 \
  redis:7-alpine@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99 >/dev/null

ready=0
for ((attempt = 0; attempt < 90; attempt++)); do
  if docker exec "$pg_name" pg_isready -h 127.0.0.1 -U nessops >/dev/null 2>&1 &&
    [[ "$(docker exec "$redis_name" redis-cli ping 2>/dev/null)" == PONG ]]; then
    ready=1
    break
  fi
  sleep 2
done
[[ "$ready" == 1 ]] || { echo 'Local Hub dependencies did not become ready' >&2; exit 1; }

docker cp "$repo_root/app/backend/sql/." "$pg_name:/tmp/sql"
for script in 000_init.sql 001_schema.sql 002_push_subscriptions.sql 003_glpi_ticket_post_reservations.sql; do
  docker exec "$pg_name" psql -v ON_ERROR_STOP=1 -U nessops -d nessops \
    -f "/tmp/sql/$script" >/dev/null
done
docker exec "$pg_name" psql -v ON_ERROR_STOP=1 -U nessops -d nessops \
  -At -c 'SELECT id FROM n_infraops_incident_actions LIMIT 0' >/dev/null

cd "$repo_root/app/backend"
NINF_LOCAL_FLOW_TEST=1 \
NINF_DATABASE_URL='postgresql+asyncpg://nessops:local-flow-only@127.0.0.1:42561/nessops' \
NINF_REDIS_URL='redis://127.0.0.1:42562/0' \
NINF_CELERY_BROKER_URL='redis://127.0.0.1:42562/1' \
NINF_GEMINI_API_KEY= NINF_ALERT_NOTIFICATIONS_ENABLED=false \
python -m pytest tests/test_hub_local_flow.py -q
