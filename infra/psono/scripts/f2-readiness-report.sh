#!/usr/bin/env bash
# Read-only F2 inventory. It prints status only, never credentials or MFA data.
set -Eeuo pipefail

readonly stack_dir="${PSONO_STACK_DIR:-/opt/ness-os-psono}"
readonly settings_file="${PSONO_SETTINGS_FILE:-${stack_dir}/runtime/settings.yaml}"
readonly psono_container="${PSONO_CONTAINER:-ness-psono}"
readonly database_container="${PSONO_DATABASE_CONTAINER:-ness-psono-db}"
readonly public_url="${PSONO_PUBLIC_URL:-https://cofre.ness.com.br}"

for command in curl docker grep stat systemctl; do
  command -v "${command}" >/dev/null || { echo "missing command: ${command}" >&2; exit 1; }
done
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 2; }
[[ -f ${settings_file} && ! -L ${settings_file} ]] || {
  echo 'psono settings are unavailable' >&2
  exit 3
}

yes_no() {
  if "$@"; then printf 'yes'; else printf 'no'; fi
}

container_health() {
  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$1"
}

readonly sql="
WITH custodians(username, label) AS (
  VALUES ('resper@ness.com.br', 'resper'), ('iaraujo@ness.com.br', 'iaraujo')
), status AS (
  SELECT c.label,
         COALESCE(u.is_active, false) AS active,
         COALESCE(u.is_superuser, false) AS superuser,
         COALESCE(u.require_password_change, true) AS password_change_required,
         COALESCE(
           u.google_authenticator_enabled OR u.duo_enabled OR
           u.yubikey_otp_enabled OR u.webauthn_enabled,
           false
         ) AS mfa,
         u.last_login IS NOT NULL AS has_logged_in,
         u.id
    FROM custodians c
    LEFT JOIN restapi_user u ON u.username = c.username
)
SELECT 'custodian_' || label || '_active=' || CASE WHEN active THEN 'yes' ELSE 'no' END FROM status
UNION ALL
SELECT 'custodian_' || label || '_superuser=' || CASE WHEN superuser THEN 'yes' ELSE 'no' END FROM status
UNION ALL
SELECT 'custodian_' || label || '_password_change_required=' || CASE WHEN password_change_required THEN 'yes' ELSE 'no' END FROM status
UNION ALL
SELECT 'custodian_' || label || '_mfa=' || CASE WHEN mfa THEN 'yes' ELSE 'no' END FROM status
UNION ALL
SELECT 'custodian_' || label || '_has_logged_in=' || CASE WHEN has_logged_in THEN 'yes' ELSE 'no' END FROM status
UNION ALL
SELECT 'custodian_' || label || '_recovery_codes=' || COUNT(rc.id)::text
  FROM status
  LEFT JOIN restapi_recovery_code rc ON rc.user_id = status.id
 GROUP BY label
UNION ALL
SELECT 'emergency_code_count=' || COUNT(*)::text FROM restapi_emergency_code
ORDER BY 1;
"

printf 'psono_f2_readiness_at=%s\n' "$(date --iso-8601=seconds)"
printf 'psono_health=%s\n' "$(container_health "${psono_container}")"
printf 'database_health=%s\n' "$(container_health "${database_container}")"
printf 'https_health=%s\n' "$(yes_no curl --fail --silent --show-error --output /dev/null --max-time 10 "${public_url%/}/server/info/")"
printf 'backup_timer_active=%s\n' "$(yes_no systemctl is-active --quiet ness-psono-backup.timer)"
printf 'last_backup_result=%s\n' "$(systemctl show ness-psono-backup.service -p Result --value)"
printf 'psono_env_permissions=%s\n' "$(stat -c '%U:%G:%a' /etc/ness-os/psono.env)"
printf 'backup_env_permissions=%s\n' "$(stat -c '%U:%G:%a' /etc/ness-os/backup-s3.env)"
printf 'registration_enabled=%s\n' "$(yes_no grep -Fqx 'ALLOW_REGISTRATION: true' "${settings_file}")"
printf 'lost_password_enabled=%s\n' "$(yes_no grep -Fqx 'ALLOW_LOST_PASSWORD: true' "${settings_file}")"
printf 'smtp_configured=%s\n' "$(yes_no grep -Fqx "EMAIL_HOST: 'smtp.resend.com'" "${settings_file}")"
printf 'smtp_credentials_present=%s\n' "$(yes_no grep -Eq '^RESEND_API_KEY=.+$' /etc/ness-os/psono.env)"
printf 'multifactor_enforced=%s\n' "$(yes_no grep -Fqx 'MULTIFACTOR_ENABLED: true' "${settings_file}")"

docker exec "${database_container}" psql -X -v ON_ERROR_STOP=1 -U psono -d psono -Atc "${sql}"
echo 'psono_f2_readiness_report=PASS'
