#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
psono="${repo_root}/infra/psono"

for file in \
  docker-compose.yml Caddyfile settings.yaml.example config.json.example \
  docker-compose.aiops.yml scripts/bootstrap-secrets.sh scripts/bootstrap-admin.sh \
  scripts/render-config.sh scripts/integrate-aiops-caddy.sh \
  scripts/init-backup-repository.sh scripts/backup.sh scripts/restore-verify.sh \
  scripts/f2-readiness-report.sh scripts/mfa-readiness.sh \
  systemd/ness-psono-backup.service systemd/ness-psono-backup.timer; do
  [[ -s ${psono}/${file} ]] || { echo "missing ${file}" >&2; exit 1; }
done

grep -q 'postgres:17-alpine@sha256:' "${psono}/docker-compose.yml"
grep -q 'psono/psono-combo:latest@sha256:' "${psono}/docker-compose.yml"
grep -q 'internal: true' "${psono}/docker-compose.yml"
if grep -Eq 'POSTGRES_PASSWORD:[[:space:]]*[^$]' "${psono}/docker-compose.yml"; then
  echo 'literal PostgreSQL password found in Compose' >&2
  exit 1
fi
grep -q 'PSONO_POSTGRES_ENV_FILE' "${psono}/docker-compose.yml"
grep -q 'Host: \$${PSONO_DOMAIN}' "${psono}/docker-compose.yml"
for caddy_source in \
  "${psono}/Caddyfile" \
  "${psono}/branding/shared-caddy-cache-migration.patch" \
  "${repo_root}/app/Caddyfile"; do
  if grep -q 'Clear-Site-Data' "${caddy_source}"; then
    echo "temporary Clear-Site-Data remains in ${caddy_source}" >&2
    exit 1
  fi
done
grep -q '/js/language-default.js /portal /portal/' "${repo_root}/app/Caddyfile"
grep -q 'app_ninf-net' "${psono}/docker-compose.aiops.yml"
grep -q 'POSTGRES_PASSWORD=' "${psono}/scripts/render-config.sh"
grep -q 'PSONO_MULTIFACTOR_ENABLED=false' "${psono}/scripts/bootstrap-secrets.sh"
grep -q 'must be root-owned' "${psono}/scripts/render-config.sh"
grep -q 'chmod 0644.*config.json' "${psono}/scripts/render-config.sh"
grep -q 'PSONO_MULTIFACTOR_ENABLED must be true or false' "${psono}/scripts/render-config.sh"
grep -q "ALLOWED_SECOND_FACTORS: \['google_authenticator', 'webauthn'\]" \
  "${psono}/scripts/render-config.sh"
grep -q 'restic check' "${psono}/scripts/backup.sh"
grep -q 'etc/ness-os/psono.env' "${psono}/scripts/backup.sh"
grep -q 'psono_restore_verify=PASS' "${psono}/scripts/restore-verify.sh"
grep -q 'Read-only F2 inventory' "${psono}/scripts/f2-readiness-report.sh"
grep -q 'restapi_recovery_code' "${psono}/scripts/f2-readiness-report.sh"
grep -q 'restapi_emergency_code' "${psono}/scripts/f2-readiness-report.sh"
grep -q 'multifactor_enforced=' "${psono}/scripts/f2-readiness-report.sh"
grep -q 'smtp_credentials_present=' "${psono}/scripts/f2-readiness-report.sh"
grep -q 'psono_f2_readiness=FAIL' "${psono}/scripts/f2-readiness-report.sh"
grep -q 'PSONO_RECOVERY_TEST_EVIDENCE' "${psono}/scripts/f2-readiness-report.sh"
grep -q 'custodian_${custodian}_mfa' "${psono}/scripts/mfa-readiness.sh"
grep -q 'custodian_${custodian}_recovery_codes' "${psono}/scripts/mfa-readiness.sh"
grep -q 'emergency_code_count' "${psono}/scripts/f2-readiness-report.sh"
if grep -Eq '(authkey|private_key|secret_key|emergency_data|verifier)[[:space:]]*(,|FROM|=)' \
    "${psono}/scripts/f2-readiness-report.sh"; then
  echo 'F2 readiness report reads secret-bearing fields' >&2
  exit 1
fi

bash_syntax_check() { tr -d '\r' < "$1" | bash -n; }
bash_syntax_check "${psono}/scripts/render-config.sh"
bash_syntax_check "${psono}/scripts/bootstrap-secrets.sh"
bash_syntax_check "${psono}/scripts/bootstrap-admin.sh"
bash_syntax_check "${psono}/scripts/integrate-aiops-caddy.sh"
bash_syntax_check "${psono}/scripts/init-backup-repository.sh"
bash_syntax_check "${psono}/scripts/backup.sh"
bash_syntax_check "${psono}/scripts/restore-verify.sh"
bash_syntax_check "${psono}/scripts/f2-readiness-report.sh"
bash -n "${psono}/scripts/mfa-readiness.sh"

source "${psono}/scripts/mfa-readiness.sh"
good_report=$(cat <<'EOF'
custodian_resper_active=yes
custodian_resper_superuser=yes
custodian_resper_password_change_required=no
custodian_resper_mfa=yes
custodian_resper_recovery_codes=4
custodian_iaraujo_active=yes
custodian_iaraujo_superuser=yes
custodian_iaraujo_password_change_required=no
custodian_iaraujo_mfa=yes
custodian_iaraujo_recovery_codes=3
emergency_code_count=2
EOF
)
psono_mfa_readiness "${good_report}" yes yes
without_mfa="$(sed 's/custodian_resper_mfa=yes/custodian_resper_mfa=no/' <<<"${good_report}")"
if psono_mfa_readiness "${without_mfa}" yes yes; then
  echo 'readiness passed with an administrator missing MFA' >&2
  exit 1
fi
without_recovery="$(sed 's/custodian_resper_recovery_codes=4/custodian_resper_recovery_codes=0/' <<<"${good_report}")"
if psono_mfa_readiness "${without_recovery}" yes yes; then
  echo 'readiness passed without recovery codes' >&2
  exit 1
fi
one_recoverable="$(sed 's/custodian_iaraujo_recovery_codes=3/custodian_iaraujo_recovery_codes=0/' <<<"${good_report}")"
if psono_mfa_readiness "${one_recoverable}" yes yes; then
  echo 'readiness passed with only one recoverable custodian' >&2
  exit 1
fi
if psono_mfa_readiness "${good_report}" yes no; then
  echo 'readiness passed without tested recovery evidence' >&2
  exit 1
fi
echo 'psono tooling static checks: PASS'
