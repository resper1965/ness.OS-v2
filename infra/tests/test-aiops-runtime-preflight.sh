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
NINF_EVOLUTION_API_KEY=do-not-print-evolution
NINF_GLPI_DB_PASSWORD=do-not-print-glpi
NINF_GLPI_DB_ROOT_PASSWORD=do-not-print-glpi-root
NINF_JWT_SECRET=do-not-print-jwt
NINF_RESEND_API_KEY=do-not-print-resend
NINF_API_IMAGE=example.invalid/ness-api@sha256:0000000000000000000000000000000000000000000000000000000000000000
NINF_FRONTEND_IMAGE=example.invalid/ness-frontend@sha256:0000000000000000000000000000000000000000000000000000000000000000
EOF

cat >"${missing_env}" <<'EOF'
NINF_AUTHENTIK_SECRET_KEY=do-not-print-authentik
NINF_DB_PASSWORD=do-not-print-database
NINF_EVOLUTION_API_KEY=do-not-print-evolution
NINF_GLPI_DB_PASSWORD=do-not-print-glpi
NINF_GLPI_DB_ROOT_PASSWORD=
NINF_JWT_SECRET=do-not-print-jwt
NINF_RESEND_API_KEY=do-not-print-resend
NINF_API_IMAGE=example.invalid/ness-api@sha256:0000000000000000000000000000000000000000000000000000000000000000
NINF_FRONTEND_IMAGE=example.invalid/ness-frontend@sha256:0000000000000000000000000000000000000000000000000000000000000000
EOF

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
  NINF_EVOLUTION_API_KEY
  NINF_GLPI_DB_PASSWORD
  NINF_GLPI_DB_ROOT_PASSWORD
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
  env_args+=("PATH=${fake_bin}:${PATH}" "AIOPS_TEST_DOCKER_LOG=${docker_log}")
  "${env_args[@]}" "$@"
}

bash -n "${preflight}"

success_output="$(run_isolated bash "${preflight}" --env-file "${complete_env}" 2>&1)"
grep -q '^required_variables=9$' <<<"${success_output}"
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

if missing_output="$(run_isolated bash "${preflight}" --env-file "${missing_env}" 2>&1)"; then
  echo 'preflight unexpectedly accepted a blank required variable' >&2
  exit 1
fi
grep -q 'missing required variables: NINF_GLPI_DB_ROOT_PASSWORD' <<<"${missing_output}"
if grep -q 'do-not-print' <<<"${missing_output}"; then
  echo 'missing-variable failure exposed a test secret' >&2
  exit 1
fi

if failure_output="$(AIOPS_TEST_CONFIG_FAIL=1 run_isolated bash "${preflight}" --env-file "${complete_env}" 2>&1)"; then
  echo 'preflight unexpectedly accepted an invalid Compose model' >&2
  exit 1
fi
grep -q 'Compose structure or merged configuration is invalid (details suppressed)' <<<"${failure_output}"
if grep -q 'do-not-print' <<<"${failure_output}"; then
  echo 'Compose failure exposed a test secret' >&2
  exit 1
fi

echo 'AIOps runtime preflight checks: PASS'
