#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
psono="${repo_root}/infra/psono"

for file in \
  docker-compose.yml Caddyfile settings.yaml.example config.json.example \
  docker-compose.aiops.yml scripts/bootstrap-secrets.sh scripts/bootstrap-admin.sh \
  scripts/render-config.sh scripts/integrate-aiops-caddy.sh \
  scripts/init-backup-repository.sh scripts/backup.sh scripts/restore-verify.sh \
  systemd/ness-psono-backup.service systemd/ness-psono-backup.timer; do
  [[ -s ${psono}/${file} ]] || { echo "missing ${file}" >&2; exit 1; }
done

grep -q 'postgres:17-alpine@sha256:' "${psono}/docker-compose.yml"
grep -q 'psono/psono-combo:latest@sha256:' "${psono}/docker-compose.yml"
grep -q 'internal: true' "${psono}/docker-compose.yml"
! grep -Eq 'POSTGRES_PASSWORD:[[:space:]]*[^$]' "${psono}/docker-compose.yml"
grep -q 'PSONO_POSTGRES_ENV_FILE' "${psono}/docker-compose.yml"
grep -q 'Host: \$${PSONO_DOMAIN}' "${psono}/docker-compose.yml"
grep -q 'app_ninf-net' "${psono}/docker-compose.aiops.yml"
grep -q 'POSTGRES_PASSWORD=' "${psono}/scripts/render-config.sh"
grep -q 'must be root-owned' "${psono}/scripts/render-config.sh"
grep -q 'chmod 0644.*config.json' "${psono}/scripts/render-config.sh"
grep -q 'restic check' "${psono}/scripts/backup.sh"
grep -q 'etc/ness-os/psono.env' "${psono}/scripts/backup.sh"
grep -q 'psono_restore_verify=PASS' "${psono}/scripts/restore-verify.sh"

bash -n "${psono}/scripts/render-config.sh"
bash -n "${psono}/scripts/bootstrap-secrets.sh"
bash -n "${psono}/scripts/bootstrap-admin.sh"
bash -n "${psono}/scripts/integrate-aiops-caddy.sh"
bash -n "${psono}/scripts/init-backup-repository.sh"
bash -n "${psono}/scripts/backup.sh"
bash -n "${psono}/scripts/restore-verify.sh"
echo 'psono tooling static checks: PASS'
