#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
app_dir="${repo_root}/app"
backend_dir="${app_dir}/backend"
preflight="${repo_root}/infra/scripts/aiops-runtime-preflight.sh"
env_file="${AIOPS_ENV_FILE:-${app_dir}/.env}"
mode=static

usage() {
  cat <<'EOF'
Usage: infra/scripts/aiops-runtime-readiness.sh [--env-file PATH] [--execute-read-only]

Default: run local static validation only. The live probes require both
--execute-read-only and AIOPS_READONLY_EXECUTE=1 on the AIOps host.
EOF
}

fail() {
  printf 'AIOps runtime readiness: FAIL: %s\n' "$1" >&2
  exit 1
}

while (($#)); do
  case "$1" in
    --env-file)
      (($# >= 2)) || fail '--env-file requires a path'
      env_file="$2"
      shift 2
      ;;
    --execute-read-only)
      mode=execute
      shift
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

compose=(docker compose --env-file "${env_file}" -f "${app_dir}/docker-compose.yml" -f "${app_dir}/docker-compose.tickets.yml")

if ! bash "${preflight}" --env-file "${env_file}" >/dev/null 2>&1; then
  fail 'preflight failed (details suppressed)'
fi
printf 'preflight=PASS\n'

probe_sources=(
  "${backend_dir}/app/integrations/zabbix_readiness.py"
  "${backend_dir}/app/integrations/glpi_readiness.py"
)
command -v python3 >/dev/null 2>&1 || fail 'python3 is required for static validation'
if ! python3 -c 'import ast, pathlib, sys; [ast.parse(pathlib.Path(p).read_text()) for p in sys.argv[1:]]' "${probe_sources[@]}" >/dev/null 2>&1; then
  fail 'readiness probe static validation failed (details suppressed)'
fi
printf 'probe_static_validation=PASS\n'

if [[ "${mode}" == static ]]; then
  printf 'probes_executed=0\n'
  printf 'AIOps runtime readiness: PASS (static)\n'
  exit 0
fi

[[ "${AIOPS_READONLY_EXECUTE:-}" == 1 ]] ||
  fail 'live probes require AIOPS_READONLY_EXECUTE=1'

if ! health_output="$(docker inspect --format '{{.Name}}={{.State.Running}}={{.State.Health.Status}}' \
    ninf-api ninf-worker-alerts ninf-worker-ml 2>/dev/null)"; then
  fail 'container health could not be inspected'
fi
for container in ninf-api ninf-worker-alerts ninf-worker-ml; do
  grep -Fxq "/${container}=true=healthy" <<<"${health_output}" ||
    fail "${container} healthcheck is not healthy or container is stopped"
done
printf 'container_health=PASS\n'

run_probe() {
  local name="$1"
  local module="$2"
  local expected="$3"
  local output

  if ! output="$("${compose[@]}" exec -T api python -m "${module}" 2>/dev/null)"; then
    fail "${name} probe failed (details suppressed)"
  fi
  [[ "${output}" =~ ${expected} ]] ||
    fail "${name} probe returned an invalid result (details suppressed)"
  printf '%s_readiness=PASS writes=0\n' "${name}"
}

run_probe zabbix app.integrations.zabbix_readiness \
  '^status=ready mode=read-only transport=json-rpc version=[0-9A-Za-z._-]+ authenticated=True visible_hosts=[0-9]+ writes=0$'
run_probe glpi app.integrations.glpi_readiness \
  '^status=ready mode=dry-run transport=private entities=[0-9]+ categories=[0-9]+ writes=0 session_closed=True$'

printf 'containers_started=0\n'
printf 'AIOps runtime readiness: PASS (live read-only)\n'
