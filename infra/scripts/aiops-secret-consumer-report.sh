#!/usr/bin/env bash
set -euo pipefail

redact_uri() {
  sed -E 's#(://[^:]+):[^@]+@#\1:[REDACTED]@#'
}

printf 'api_db='
docker exec ninf-api sh -lc 'printf "%s\n" "$NINF_DATABASE_URL"' | redact_uri
printf 'postgres_compose_password_present='
docker exec ninf-postgres sh -lc 'test -n "$POSTGRES_PASSWORD" && echo yes || echo no'

api_password="$(docker exec ninf-api sh -lc 'printf "%s" "$NINF_DATABASE_URL"' | sed -E 's#^[^:]+://[^:]+:([^@]+)@.*#\1#')"
postgres_password="$(docker exec ninf-postgres sh -lc 'printf "%s" "$POSTGRES_PASSWORD"')"

printf 'shared_database_password_consistent='
if [[ -n "${api_password}" \
  && "${api_password}" == "${postgres_password}" ]]; then
  echo yes
else
  echo no
fi
printf 'database_password_uses_known_default='
[[ "${api_password}" == changeme ]] && echo yes || echo no

unset api_password postgres_password
