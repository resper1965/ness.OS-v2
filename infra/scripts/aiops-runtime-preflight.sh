#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
app_dir="${repo_root}/app"
env_file="${AIOPS_ENV_FILE:-${app_dir}/.env}"
compose_files=(
  "${app_dir}/docker-compose.yml"
  "${app_dir}/docker-compose.tickets.yml"
)

usage() {
  cat <<'EOF'
Usage: infra/scripts/aiops-runtime-preflight.sh [--env-file PATH]

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

mapfile -t required_variables < <(
  grep -hoE '\$\{[A-Za-z_][A-Za-z0-9_]*:\?[^}]*\}' "${compose_files[@]}" |
    sed -E 's/^\$\{([A-Za-z_][A-Za-z0-9_]*):\?.*$/\1/' |
    sort -u
)
((${#required_variables[@]} > 0)) || fail 'Compose files declare no required variables'

dotenv_has_nonempty_value() {
  local variable="$1"

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
  ' "${env_file}"
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
