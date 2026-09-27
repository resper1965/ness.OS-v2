#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
runner="${repo_root}/infra/scripts/aiops-runtime-readiness.sh"
compose_file="${repo_root}/app/docker-compose.yml"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "${tmpdir}"' EXIT

env_file="${tmpdir}/runtime.env"
fake_bin="${tmpdir}/bin"
docker_log="${tmpdir}/docker.log"
mkdir -p "${fake_bin}"

cat >"${env_file}" <<'EOF'
NINF_AUTHENTIK_SECRET_KEY=runner-secret-authentik
NINF_DB_PASSWORD=runner-secret-database
NINF_EVOLUTION_API_KEY=runner-secret-evolution
NINF_GLPI_DB_PASSWORD=runner-secret-glpi-db
NINF_GLPI_DB_ROOT_PASSWORD=runner-secret-glpi-root
NINF_JWT_SECRET=runner-secret-jwt
NINF_RESEND_API_KEY=runner-secret-resend
NINF_ZABBIX_API_TOKEN=runner-secret-zabbix
NINF_GLPI_APP_TOKEN=runner-secret-glpi-app
NINF_GLPI_USER_TOKEN=runner-secret-glpi-user
EOF

cat >"${fake_bin}/docker" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >>"${AIOPS_TEST_DOCKER_LOG}"

if [[ "${1-}" == inspect ]]; then
  if [[ "${AIOPS_TEST_WORKER_UNHEALTHY:-0}" == 1 ]]; then
    printf '%s\n' '/ninf-api=healthy' '/ninf-worker-alerts=unhealthy' '/ninf-worker-ml=healthy'
  else
    printf '%s\n' '/ninf-api=healthy' '/ninf-worker-alerts=healthy' '/ninf-worker-ml=healthy'
  fi
  exit 0
fi

[[ "${1-}" == compose ]] || exit 90
if [[ "${2-}" == version ]]; then
  exit 0
fi

arguments=" $* "
if [[ "${arguments}" == *' config --quiet --no-env-resolution '* ]]; then
  exit 0
fi
for forbidden in up start run create pull restart down rm stop kill; do
  [[ "${arguments}" != *" ${forbidden} "* ]] || exit 91
done

module="${*: -1}"
case "${module}" in
  app.integrations.zabbix_readiness)
    [[ "${AIOPS_TEST_ZABBIX_FAIL:-0}" == 0 ]] || {
      echo 'runner-secret-zabbix' >&2
      exit 92
    }
    printf '%s\n' "${AIOPS_TEST_ZABBIX_OUTPUT:-status=ready mode=read-only transport=json-rpc version=7.0.0 authenticated=True visible_hosts=1 writes=0}"
    ;;
  app.integrations.glpi_readiness)
    printf '%s\n' 'status=ready mode=dry-run transport=private entities=2 categories=3 writes=0 session_closed=True'
    ;;
  *) exit 93 ;;
esac
EOF
chmod +x "${fake_bin}/docker"

run_isolated() {
  env -u AIOPS_READONLY_EXECUTE \
    PATH="${fake_bin}:${PATH}" \
    AIOPS_TEST_DOCKER_LOG="${docker_log}" \
    "$@"
}

assert_no_secrets() {
  if grep -q 'runner-secret-' <<<"$1"; then
    echo 'readiness output exposed a test secret' >&2
    return 1
  fi
}

bash -n "${runner}"

service_block() {
  awk -v target="$1" '
    $0 == "  " target ":" { active=1; next }
    active && /^  [[:alnum:]_-]+:/ { exit }
    active { print }
  ' "${compose_file}"
}

if grep -Fq '|| exit 0' "${compose_file}"; then
  echo 'a runtime healthcheck still converts failure into success' >&2
  exit 1
fi
api_health="$(service_block api)"
grep -q 'healthcheck:' <<<"${api_health}"
grep -q 'app.integrations.pipeline_health' <<<"${api_health}"
for worker in worker-alerts worker-ml; do
  worker_health="$(service_block "${worker}")"
  grep -q 'healthcheck:' <<<"${worker_health}"
  grep -q 'inspect ping' <<<"${worker_health}"
done

static_output="$(run_isolated bash "${runner}" --env-file "${env_file}" 2>&1)"
grep -q '^preflight=PASS$' <<<"${static_output}"
grep -q '^probe_static_validation=PASS$' <<<"${static_output}"
grep -q '^probes_executed=0$' <<<"${static_output}"
grep -q '^AIOps runtime readiness: PASS (static)$' <<<"${static_output}"
assert_no_secrets "${static_output}"
if grep -q ' exec ' "${docker_log}"; then
  echo 'static readiness executed a container command' >&2
  exit 1
fi

if guard_output="$(run_isolated bash "${runner}" --env-file "${env_file}" --execute-read-only 2>&1)"; then
  echo 'runner unexpectedly executed probes without the environment guard' >&2
  exit 1
fi
grep -q 'live probes require AIOPS_READONLY_EXECUTE=1' <<<"${guard_output}"
assert_no_secrets "${guard_output}"
if grep -q ' exec ' "${docker_log}"; then
  echo 'guarded readiness executed a container command' >&2
  exit 1
fi

live_output="$(run_isolated env AIOPS_READONLY_EXECUTE=1 bash "${runner}" --env-file "${env_file}" --execute-read-only 2>&1)"
grep -q '^zabbix_readiness=PASS writes=0$' <<<"${live_output}"
grep -q '^glpi_readiness=PASS writes=0$' <<<"${live_output}"
grep -q '^container_health=PASS$' <<<"${live_output}"
grep -q '^containers_started=0$' <<<"${live_output}"
grep -q '^AIOps runtime readiness: PASS (live read-only)$' <<<"${live_output}"
assert_no_secrets "${live_output}"
grep -q 'exec -T api python -m app.integrations.zabbix_readiness' "${docker_log}"
grep -q 'exec -T api python -m app.integrations.glpi_readiness' "${docker_log}"
grep -q 'inspect --format .*ninf-api ninf-worker-alerts ninf-worker-ml' "${docker_log}"
if grep -Eq '(^| )(up|start|run|create|pull|restart|down|rm|stop|kill)( |$)' "${docker_log}"; then
  echo 'read-only readiness executed a mutating Docker command' >&2
  exit 1
fi

if bad_output="$(run_isolated env AIOPS_TEST_ZABBIX_OUTPUT=runner-secret-zabbix AIOPS_READONLY_EXECUTE=1 bash "${runner}" --env-file "${env_file}" --execute-read-only 2>&1)"; then
  echo 'runner unexpectedly accepted malformed probe output' >&2
  exit 1
fi
grep -q 'zabbix probe returned an invalid result (details suppressed)' <<<"${bad_output}"
assert_no_secrets "${bad_output}"

if failed_output="$(run_isolated env AIOPS_TEST_ZABBIX_FAIL=1 AIOPS_READONLY_EXECUTE=1 bash "${runner}" --env-file "${env_file}" --execute-read-only 2>&1)"; then
  echo 'runner unexpectedly accepted a failed probe' >&2
  exit 1
fi
grep -q 'zabbix probe failed (details suppressed)' <<<"${failed_output}"
assert_no_secrets "${failed_output}"

if unhealthy_output="$(run_isolated env AIOPS_TEST_WORKER_UNHEALTHY=1 AIOPS_READONLY_EXECUTE=1 bash "${runner}" --env-file "${env_file}" --execute-read-only 2>&1)"; then
  echo 'runner unexpectedly accepted an unhealthy worker' >&2
  exit 1
fi
grep -q 'ninf-worker-alerts healthcheck is not healthy' <<<"${unhealthy_output}"
assert_no_secrets "${unhealthy_output}"

echo 'AIOps runtime readiness runner checks: PASS'
