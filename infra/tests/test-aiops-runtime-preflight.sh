#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
preflight="${repo_root}/infra/scripts/aiops-runtime-preflight.sh"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "${tmpdir}"' EXIT

complete_env="${tmpdir}/complete.env"
missing_env="${tmpdir}/missing.env"
fake_bin="${tmpdir}/bin"
docker_log="${tmpdir}/docker.log"
mkdir -p "${fake_bin}"

cat >"${complete_env}" <<'EOF'
NINF_AUTHENTIK_SECRET_KEY=do-not-print-authentik
NINF_DB_PASSWORD=do-not-print-database
NINF_JWT_SECRET=do-not-print-jwt
NINF_RESEND_API_KEY=do-not-print-resend
NINF_API_IMAGE=example.invalid/ness-api@sha256:0000000000000000000000000000000000000000000000000000000000000000
NINF_FRONTEND_IMAGE=example.invalid/ness-frontend@sha256:0000000000000000000000000000000000000000000000000000000000000000
EOF

cat >"${missing_env}" <<'EOF'
NINF_AUTHENTIK_SECRET_KEY=do-not-print-authentik
NINF_DB_PASSWORD=do-not-print-database
NINF_JWT_SECRET=
NINF_RESEND_API_KEY=do-not-print-resend
NINF_API_IMAGE=example.invalid/ness-api@sha256:0000000000000000000000000000000000000000000000000000000000000000
NINF_FRONTEND_IMAGE=example.invalid/ness-frontend@sha256:0000000000000000000000000000000000000000000000000000000000000000
EOF

glpi_db_env="${tmpdir}/glpi-db.env"
glpi_db_env_blank="${tmpdir}/glpi-db-blank.env"
leaky_env="${tmpdir}/leaky.env"
glpi_app_env="${tmpdir}/glpi-app.env"
glpi_app_env_leaky="${tmpdir}/glpi-app-leaky.env"
printf '%s\n' MYSQL_ROOT_PASSWORD=do-not-print-root MYSQL_PASSWORD=do-not-print-db >"${glpi_db_env}"
printf '%s\n' MYSQL_ROOT_PASSWORD= MYSQL_PASSWORD=do-not-print-db >"${glpi_db_env_blank}"
printf '%s\n' DB_PASSWORD=do-not-print-db >"${glpi_app_env}"
tunnel_env="${tmpdir}/cloudflared-glpi.env"
printf '%s\n' TUNNEL_TOKEN=do-not-print-tunnel >"${tunnel_env}"
printf '%s\n' DB_PASSWORD=do-not-print-db MYSQL_ROOT_PASSWORD=do-not-print-root >"${glpi_app_env_leaky}"
{ cat "${complete_env}"; printf '%s\n' NINF_GLPI_DB_ROOT_PASSWORD=do-not-print-leak; } >"${leaky_env}"

cat >"${fake_bin}/docker" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >>"${AIOPS_TEST_DOCKER_LOG}"

[[ "${1-}" == compose ]] || exit 90
if [[ "${2-}" == version ]]; then
  exit 0
fi

arguments=" $* "
[[ "${arguments}" == *' config --quiet --no-env-resolution '* ]] || exit 91
for forbidden in up start run create pull exec restart down; do
  [[ "${arguments}" != *" ${forbidden} "* ]] || exit 92
done
[[ "${AIOPS_TEST_CONFIG_FAIL:-0}" == 0 ]] || exit 93
EOF
chmod +x "${fake_bin}/docker"

unset_required=(
  NINF_AUTHENTIK_SECRET_KEY
  NINF_DB_PASSWORD
  NINF_JWT_SECRET
  NINF_RESEND_API_KEY
  NINF_API_IMAGE
  NINF_FRONTEND_IMAGE
)

run_isolated() {
  local variable
  local env_args=(env)
  for variable in "${unset_required[@]}"; do
    env_args+=(-u "${variable}")
  done
  env_args+=("PATH=${fake_bin}:${PATH}" "AIOPS_TEST_DOCKER_LOG=${docker_log}" "AIOPS_CLOUDFLARED_GLPI_ENV_FILE=${AIOPS_CLOUDFLARED_GLPI_ENV_FILE:-${tunnel_env}}")
  "${env_args[@]}" "$@"
}

bash -n "${preflight}"

success_output="$(run_isolated bash "${preflight}" --env-file "${complete_env}" --glpi-db-env "${glpi_db_env}" --glpi-app-env "${glpi_app_env}" 2>&1)"
grep -q '^required_variables=6$' <<<"${success_output}"
grep -q '^compose_files=2$' <<<"${success_output}"
grep -q '^containers_started=0$' <<<"${success_output}"
grep -q '^AIOps runtime preflight: PASS$' <<<"${success_output}"
if grep -q 'do-not-print' <<<"${success_output}"; then
  echo 'successful preflight exposed a test secret' >&2
  exit 1
fi
grep -q 'config --quiet --no-env-resolution' "${docker_log}"
if grep -Eq '(^| )(up|start|run|create|pull|exec|restart|down)( |$)' "${docker_log}"; then
  echo 'preflight executed a mutating Docker command' >&2
  exit 1
fi

if missing_output="$(run_isolated bash "${preflight}" --env-file "${missing_env}" --glpi-db-env "${glpi_db_env}" --glpi-app-env "${glpi_app_env}" 2>&1)"; then
  echo 'preflight unexpectedly accepted a blank required variable' >&2
  exit 1
fi
grep -q 'missing required variables: NINF_JWT_SECRET' <<<"${missing_output}"
if grep -q 'do-not-print' <<<"${missing_output}"; then
  echo 'missing-variable failure exposed a test secret' >&2
  exit 1
fi

if blank_output="$(run_isolated bash "${preflight}" --env-file "${complete_env}" --glpi-db-env "${glpi_db_env_blank}" --glpi-app-env "${glpi_app_env}" 2>&1)"; then
  echo 'preflight accepted a blank GLPI database secret' >&2
  exit 1
fi
grep -q 'missing GLPI database variables: MYSQL_ROOT_PASSWORD' <<<"${blank_output}"

glpi_app_env_diff="${tmpdir}/glpi-app-diff.env"
printf '%s\n' DB_PASSWORD=do-not-print-other >"${glpi_app_env_diff}"
if diff_out="$(run_isolated bash "${preflight}" --env-file "${complete_env}" --glpi-db-env "${glpi_db_env}" --glpi-app-env "${glpi_app_env_diff}" 2>&1)"; then
  echo 'preflight accepted different MYSQL_PASSWORD and DB_PASSWORD' >&2
  exit 1
fi
grep -q 'MYSQL_PASSWORD (glpi-db.env) and DB_PASSWORD (glpi-app.env) differ' <<<"${diff_out}"
if grep -q 'do-not-print' <<<"${diff_out}"; then echo 'mismatch check exposed a secret' >&2; exit 1; fi
# aspas externas não contam como diferença
printf '%s\n' 'DB_PASSWORD="do-not-print-db"' >"${tmpdir}/glpi-app-quoted.env"
run_isolated bash "${preflight}" --env-file "${complete_env}" --glpi-db-env "${glpi_db_env}" --glpi-app-env "${tmpdir}/glpi-app-quoted.env" >/dev/null 2>&1

if tunnel_out="$(AIOPS_CLOUDFLARED_GLPI_ENV_FILE="${tmpdir}/absent.env" run_isolated bash "${preflight}" --env-file "${complete_env}" --glpi-db-env "${glpi_db_env}" --glpi-app-env "${glpi_app_env}" 2>&1)"; then
  echo 'preflight accepted a missing tunnel token file' >&2
  exit 1
fi
grep -q 'missing TUNNEL_TOKEN' <<<"${tunnel_out}"

if app_leak="$(run_isolated bash "${preflight}" --env-file "${complete_env}" --glpi-db-env "${glpi_db_env}" --glpi-app-env "${glpi_app_env_leaky}" 2>&1)"; then
  echo 'preflight accepted the root password in the GLPI app file' >&2
  exit 1
fi
grep -q 'MYSQL_ROOT_PASSWORD must not be in the GLPI app environment file' <<<"${app_leak}"

if leak_output="$(run_isolated bash "${preflight}" --env-file "${leaky_env}" --glpi-db-env "${glpi_db_env}" --glpi-app-env "${glpi_app_env}" 2>&1)"; then
  echo 'preflight accepted the GLPI root password inside the Hub env file' >&2
  exit 1
fi
grep -q 'NINF_GLPI_DB_ROOT_PASSWORD must not be in the Hub environment file' <<<"${leak_output}"
if grep -q 'do-not-print' <<<"${blank_output}${leak_output}"; then
  echo 'GLPI secret check exposed a test secret' >&2
  exit 1
fi

if failure_output="$(AIOPS_TEST_CONFIG_FAIL=1 run_isolated bash "${preflight}" --env-file "${complete_env}" --glpi-db-env "${glpi_db_env}" --glpi-app-env "${glpi_app_env}" 2>&1)"; then
  echo 'preflight unexpectedly accepted an invalid Compose model' >&2
  exit 1
fi
grep -q 'Compose structure or merged configuration is invalid (details suppressed)' <<<"${failure_output}"
if grep -q 'do-not-print' <<<"${failure_output}"; then
  echo 'Compose failure exposed a test secret' >&2
  exit 1
fi

echo 'AIOps runtime preflight checks: PASS'
