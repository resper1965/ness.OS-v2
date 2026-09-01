#!/usr/bin/env bash
set -euo pipefail

redact_uri() {
  sed -E 's#(://[^:]+):[^@]+@#\1:[REDACTED]@#'
}

printf 'api_db='
docker exec ninf-api sh -lc 'printf "%s\n" "$NINF_DATABASE_URL"' | redact_uri
printf 'evolution_db='
docker exec ninf-evolution sh -lc 'printf "%s\n" "$DATABASE_CONNECTION_URI"' | redact_uri
printf 'authentik_db_user='
docker exec ninf-authentik-server sh -lc 'printf "%s\n" "$AUTHENTIK_POSTGRESQL__USER"'
printf 'authentik_db_name='
docker exec ninf-authentik-server sh -lc 'printf "%s\n" "$AUTHENTIK_POSTGRESQL__NAME"'
printf 'authentik_secret_present='
docker exec ninf-authentik-server sh -lc 'test -n "$AUTHENTIK_SECRET_KEY" && echo yes || echo no'
printf 'postgres_compose_password_present='
docker exec ninf-postgres sh -lc 'test -n "$POSTGRES_PASSWORD" && echo yes || echo no'

api_password="$(docker exec ninf-api sh -lc 'printf "%s" "$NINF_DATABASE_URL"' | sed -E 's#^[^:]+://[^:]+:([^@]+)@.*#\1#')"
evolution_password="$(docker exec ninf-evolution sh -lc 'printf "%s" "$DATABASE_CONNECTION_URI"' | sed -E 's#^[^:]+://[^:]+:([^@]+)@.*#\1#')"
authentik_password="$(docker exec ninf-authentik-server sh -lc 'printf "%s" "$AUTHENTIK_POSTGRESQL__PASSWORD"')"
postgres_password="$(docker exec ninf-postgres sh -lc 'printf "%s" "$POSTGRES_PASSWORD"')"
authentik_secret="$(docker exec ninf-authentik-server sh -lc 'printf "%s" "$AUTHENTIK_SECRET_KEY"')"

printf 'shared_database_password_consistent='
if [[ -n "${api_password}" && "${api_password}" == "${evolution_password}" \
  && "${api_password}" == "${authentik_password}" \
  && "${api_password}" == "${postgres_password}" ]]; then
  echo yes
else
  echo no
fi
printf 'database_password_uses_known_default='
[[ "${api_password}" == changeme ]] && echo yes || echo no
printf 'authentik_secret_uses_compose_default='
[[ "${authentik_secret}" == 'f1e5CICu!vyh_supersecret' ]] && echo yes || echo no

unset api_password evolution_password authentik_password postgres_password authentik_secret
