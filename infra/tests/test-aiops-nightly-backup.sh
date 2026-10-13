#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source_script="${repo_root}/infra/scripts/aiops-nightly-backup.sh"
deployment_script="${repo_root}/infra/scripts/aiops-deployment-backup.sh"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "${tmpdir}"' EXIT

bash -n "${source_script}" "${deployment_script}"
if grep -Eq 'docker exec (ninf-postgres|-i ninf-postgres)' "${deployment_script}"; then
  echo 'deployment backup bypasses Compose for PostgreSQL collection' >&2
  exit 1
fi
grep -q 'exec -T postgres' "${deployment_script}"

fake_bin="${tmpdir}/bin"
test_app="${tmpdir}/app"
test_backup="${tmpdir}/backup/nightly"
mkdir -p "${fake_bin}" "${test_app}"
for file in .env Caddyfile docker-compose.yml docker-compose.tickets.yml; do
  printf 'fixture\n' >"${test_app}/${file}"
done

sed \
  -e "s|backup_root=\"/opt/n-infraops/backups/nightly\"|backup_root=\"${test_backup}\"|" \
  -e "s|app_dir=\"/opt/n-infraops/app\"|app_dir=\"${test_app}\"|" \
  -e "s|lock_file=\"/run/lock/ness-aiops-backup.lock\"|lock_file=\"${tmpdir}/backup.lock\"|" \
  -e 's|stamp="$(date +%Y%m%dT%H%M%S%z)"|stamp="${AIOPS_TEST_STAMP:-fixture}"|' \
  -e "s|/usr/local/sbin/ness-aiops-deployment-backup|${tmpdir}/deployment-backup.sh|" \
  -e 's/install -d -o root -g root -m 700/install -d -m 700/' \
  "${source_script}" >"${tmpdir}/aiops-nightly-backup.sh"

cat >"${tmpdir}/deployment-backup.sh" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
destination="$1"
for artifact in deployment-app.tar.gz deployment-runtime.tar.gz deployment-images.json \
  deployment-local-images.tar.gz deployment-hub-database.tar.gz; do
  [[ "${AIOPS_TEST_OMIT_ARTIFACT:-}" != "${artifact}" ]] || continue
  if [[ "${artifact}" == *.tar.gz ]]; then
    tar -czf "${destination}/${artifact}" --files-from /dev/null
  else
    printf '[]\n' >"${destination}/${artifact}"
  fi
done
EOF
chmod +x "${tmpdir}/deployment-backup.sh"

cat >"${fake_bin}/flock" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat >"${fake_bin}/df" <<'EOF'
#!/usr/bin/env bash
printf 'Avail\n999999999\n'
EOF
cat >"${fake_bin}/install" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${1-}" == -d ]] || exit 95
skip_value=0
for argument in "$@"; do
  if (( skip_value )); then
    skip_value=0
    continue
  fi
  case "${argument}" in
    -m|-o|-g) skip_value=1 ;;
    -*) ;;
    *) mkdir -p "${argument}" ;;
  esac
done
EOF
chmod +x "${fake_bin}/flock" "${fake_bin}/df" "${fake_bin}/install"

cat >"${fake_bin}/docker" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >>"${AIOPS_TEST_DOCKER_LOG}"
arguments=" $* "

if [[ "${1-}" == compose ]]; then
  if [[ "${arguments}" == *' exec '* ]]; then
    case "${arguments}" in
      *pg_dumpall*) printf 'CREATE ROLE fixture;\n' ;;
      *'psql -At'*) printf 'nessops\n' ;;
      *pg_dump*) [[ "${AIOPS_TEST_EMPTY_DUMP:-0}" == 1 ]] || printf 'fixture database dump\n' ;;
      *mariadb-dump*) printf 'CREATE DATABASE fixture;\n' ;;
      *pg_restore*) exit 0 ;;
      *) exit 91 ;;
    esac
  elif [[ "${arguments}" == *' ps -q api '* ]]; then
    printf 'api-id\n'
  elif [[ "${arguments}" == *' ps -aq '* ]]; then
    printf 'api-id\n'
  fi
  exit 0
fi

case "${1-}" in
  exec)
    case "${arguments}" in
      *pg_dumpall*) printf 'CREATE ROLE fixture;\n' ;;
      *'psql -At'*) printf 'nessops\n' ;;
      *pg_dump*) printf 'fixture database dump\n' ;;
      *mariadb-dump*) printf 'CREATE DATABASE fixture;\n' ;;
      *pg_restore*) exit 0 ;;
      *) exit 91 ;;
    esac
    ;;
  ps)
    printf 'glpi-id\n'
    ;;
  inspect)
    if [[ "${arguments}" == *'.State.Running'* ]]; then
      printf 'false\n'
    elif [[ "${arguments}" == *'.NetworkSettings.Networks'* ]]; then
      printf 'app_ninf-net\n'
    elif [[ "${arguments}" == *'.Mounts'* ]]; then
      printf 'app_n8n-data\n'
      [[ "${AIOPS_TEST_OMIT_GLPI_STATE:-0}" == 1 ]] || printf 'app_glpi-state\n'
    fi
    ;;
  network)
    [[ "${2-}" == inspect && "${3-}" != bridge ]] || {
      echo 'network docker0 missing' >&2
      exit 92
    }
    printf '[{"Name":"%s"}]\n' "${3}"
    ;;
  run)
    if [[ "${arguments}" != *' --network app_ninf-net '* ]]; then
      echo 'failed to create endpoint: network docker0 missing' >&2
      exit 93
    fi
    for argument in "$@"; do
      if [[ "${argument}" == *:/backup ]]; then
        backup_path="${argument%:/backup}"
      elif [[ "${argument}" == *:/source:ro ]]; then
        volume="${argument%%:/source:ro}"
      fi
    done
    mkdir -p "${backup_path}"
    tar -czf "${backup_path}/${volume}.tar.gz" --files-from /dev/null
    ;;
  stop|start)
    ;;
  *) exit 94 ;;
esac
EOF
chmod +x "${fake_bin}/docker"

cat >"${fake_bin}/sha256sum" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${1-}" == -c ]]; then
  exec "${AIOPS_TEST_REAL_SHA256SUM}" "$@"
fi
if [[ "${AIOPS_TEST_EMPTY_CHECKSUMS:-0}" == 1 ]]; then
  exit 0
fi
exec "${AIOPS_TEST_REAL_SHA256SUM}" "$@"
EOF
chmod +x "${fake_bin}/sha256sum"

real_sha256sum="$(command -v sha256sum)"
docker_log="${tmpdir}/docker.log"
run_backup() {
  env \
    PATH="${fake_bin}:${PATH}" \
    AIOPS_TEST_STAMP="${AIOPS_TEST_STAMP:-fixture}" \
    AIOPS_TEST_DOCKER_LOG="${docker_log}" \
    AIOPS_TEST_REAL_SHA256SUM="${real_sha256sum}" \
    "$@" bash "${tmpdir}/aiops-nightly-backup.sh"
}

if ! output="$(AIOPS_TEST_STAMP=fixture-success run_backup 2>&1)"; then
  printf 'successful backup fixture failed:\n%s\n' "${output}" >&2
  exit 1
fi
backup_dir="${test_backup}/fixture-success"
[[ -f "${backup_dir}/COMPLETED" ]]
for artifact in postgres/globals.sql.gz postgres/nessops.dump glpi-all-databases.sql.gz \
  app-config.tar.gz deployment-app.tar.gz deployment-runtime.tar.gz deployment-images.json \
  deployment-local-images.tar.gz deployment-hub-database.tar.gz backup-set-manifest.json \
  volumes/app_glpi-state.tar.gz SHA256SUMS; do
  [[ -s "${backup_dir}/${artifact}" ]] || {
    echo "successful backup omitted or emptied ${artifact}" >&2
    exit 1
  }
done
grep -q '"backup_set_id":"fixture-success"' "${backup_dir}/backup-set-manifest.json"
grep -Fq './backup-set-manifest.json' "${backup_dir}/SHA256SUMS"
grep -q '^network inspect app_ninf-net$' "${docker_log}"
grep -q '^run --rm --network app_ninf-net ' "${docker_log}"

expect_incomplete_backup() {
  local label="$1"
  shift
  if output="$(AIOPS_TEST_STAMP="fixture-${label}" run_backup "$@" 2>&1)"; then
    echo "backup unexpectedly succeeded with ${label}" >&2
    exit 1
  fi
  [[ ! -e "${test_backup}/fixture-${label}/COMPLETED" ]] || {
    echo "backup marked incomplete ${label} set as completed" >&2
    exit 1
  }
}

expect_incomplete_backup empty-dump AIOPS_TEST_EMPTY_DUMP=1
expect_incomplete_backup missing-manifest AIOPS_TEST_OMIT_ARTIFACT=deployment-images.json
expect_incomplete_backup empty-checksums AIOPS_TEST_EMPTY_CHECKSUMS=1
expect_incomplete_backup missing-glpi-state AIOPS_TEST_OMIT_GLPI_STATE=1

echo 'AIOps nightly backup checks: PASS'
