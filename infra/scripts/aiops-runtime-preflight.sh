#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
app_dir="${repo_root}/app"
env_file="${AIOPS_ENV_FILE:-${app_dir}/.env}"
glpi_db_env_file="${AIOPS_GLPI_DB_ENV_FILE:-/etc/ness-os/glpi-db.env}"
glpi_app_env_file="${AIOPS_GLPI_APP_ENV_FILE:-/etc/ness-os/glpi-app.env}"
compose_files=(
  "${app_dir}/docker-compose.yml"
  "${app_dir}/docker-compose.tickets.yml"
)

usage() {
  cat <<'EOF'
Usage: infra/scripts/aiops-runtime-preflight.sh [--env-file PATH] [--glpi-db-env PATH] [--glpi-app-env PATH]

Validates the local AIOps Compose model and required environment variable
presence without printing values, contacting production, or starting containers.
EOF
}

fail() {
  printf 'AIOps runtime preflight: FAIL: %s\n' "$1" >&2
  exit 1
}

while (($#)); do
  case "$1" in
    --env-file)
      (($# >= 2)) || fail '--env-file requires a path'
      env_file="$2"
      shift 2
      ;;
    --glpi-db-env)
      (($# >= 2)) || fail '--glpi-db-env requires a path'
      glpi_db_env_file="$2"
      shift 2
      ;;
    --glpi-app-env)
      (($# >= 2)) || fail '--glpi-app-env requires a path'
      glpi_app_env_file="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

for compose_file in "${compose_files[@]}"; do
  [[ -r "${compose_file}" ]] || fail "Compose file is not readable: ${compose_file}"
done
[[ -r "${env_file}" ]] || fail "environment file is not readable: ${env_file}"
[[ -r "${glpi_app_env_file}" ]] || fail "GLPI app environment file is not readable: ${glpi_app_env_file}"
[[ -r "${glpi_db_env_file}" ]] || fail "GLPI database environment file is not readable: ${glpi_db_env_file}"

mapfile -t required_variables < <(
  grep -hoE '\$\{[A-Za-z_][A-Za-z0-9_]*:\?[^}]*\}' "${compose_files[@]}" |
    sed -E 's/^\$\{([A-Za-z_][A-Za-z0-9_]*):\?.*$/\1/' |
    sort -u
)
((${#required_variables[@]} > 0)) || fail 'Compose files declare no required variables'

dotenv_has_nonempty_value() {
  local variable="$1"
  local file="${2:-${env_file}}"

  awk -v wanted="${variable}" '
    function trim(value) {
      sub(/^[[:space:]]+/, "", value)
      sub(/[[:space:]]+$/, "", value)
      return value
    }
    {
      line = $0
      sub(/\r$/, "", line)
      if (line ~ /^[[:space:]]*(#|$)/) next
      sub(/^[[:space:]]*export[[:space:]]+/, "", line)
      separator = index(line, "=")
      if (!separator) next
      key = trim(substr(line, 1, separator - 1))
      if (key != wanted) next
      value = trim(substr(line, separator + 1))
      if (value == "\"\"" || value == "\047\047") value = ""
      present = length(value) > 0
    }
    END { exit present ? 0 : 1 }
  ' "${file}"
}

missing_variables=()
for variable in "${required_variables[@]}"; do
  if [[ -z "${!variable-}" ]] && ! dotenv_has_nonempty_value "${variable}"; then
    missing_variables+=("${variable}")
  fi
done

if ((${#missing_variables[@]})); then
  fail "missing required variables: ${missing_variables[*]}"
fi

# GLPI database credentials live only in the GLPI-private file. The Hub receives the whole
# app/.env, so they must be absent there (ADR 0020 follow-up, Hub <-> GLPI isolation).
missing_glpi=()
for variable in MYSQL_ROOT_PASSWORD MYSQL_PASSWORD; do
  dotenv_has_nonempty_value "${variable}" "${glpi_db_env_file}" || missing_glpi+=("${variable}")
done
dotenv_has_nonempty_value DB_PASSWORD "${glpi_app_env_file}" || missing_glpi+=(DB_PASSWORD)
if grep -Eq '^[[:space:]]*(export[[:space:]]+)?MYSQL_ROOT_PASSWORD=' "${glpi_app_env_file}"; then
  fail "MYSQL_ROOT_PASSWORD must not be in the GLPI app environment file ${glpi_app_env_file}"
fi
((${#missing_glpi[@]} == 0)) || fail "missing GLPI database variables: ${missing_glpi[*]}"
dotenv_value_hash() {
  # imprime só o hash do valor (aspas externas removidas), nunca o valor
  awk -v wanted="$1" '
    { line=$0; sub(/\r$/, "", line); sub(/^[[:space:]]*export[[:space:]]+/, "", line)
      i=index(line,"="); if(!i) next
      k=substr(line,1,i-1); gsub(/^[[:space:]]+|[[:space:]]+$/,"",k); if(k!=wanted) next
      v=substr(line,i+1); gsub(/^[[:space:]]+|[[:space:]]+$/,"",v)
      if (v ~ /^".*"$/ || v ~ /^\047.*\047$/) v=substr(v,2,length(v)-2)
      val=v }
    END { printf "%s", val }' "$2" | sha256sum | cut -d' ' -f1
}
# O banco lê MYSQL_PASSWORD e o GLPI lê DB_PASSWORD: precisam ser o mesmo valor.
[[ "$(dotenv_value_hash MYSQL_PASSWORD "${glpi_db_env_file}")" == "$(dotenv_value_hash DB_PASSWORD "${glpi_app_env_file}")" ]] \
  || fail 'MYSQL_PASSWORD (glpi-db.env) and DB_PASSWORD (glpi-app.env) differ'
for variable in NINF_GLPI_DB_ROOT_PASSWORD NINF_GLPI_DB_PASSWORD; do
  if grep -Eq "^[[:space:]]*(export[[:space:]]+)?${variable}=" "${env_file}"; then
    fail "${variable} must not be in the Hub environment file ${env_file}"
  fi
done

command -v docker >/dev/null 2>&1 || fail 'Docker CLI is not installed'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose plugin is not available'

# `config` only builds and validates the merged model. Quiet mode and suppressed
# diagnostics ensure interpolated secret values can never reach this script's output.
if ! docker compose \
  --env-file "${env_file}" \
  -f "${compose_files[0]}" \
  -f "${compose_files[1]}" \
  config --quiet --no-env-resolution >/dev/null 2>&1; then
  fail 'Compose structure or merged configuration is invalid (details suppressed)'
fi

printf 'required_variables=%d\n' "${#required_variables[@]}"
printf 'compose_files=%d\n' "${#compose_files[@]}"
printf 'containers_started=0\n'
printf 'AIOps runtime preflight: PASS\n'
