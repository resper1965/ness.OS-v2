#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly server_config="${SERVER_CONFIG:-/etc/zabbix/zabbix_server.conf}"
readonly frontend_config="${FRONTEND_CONFIG:-/etc/zabbix/web/zabbix.conf.php}"
readonly evidence_root="${EVIDENCE_ROOT:-/var/lib/ness-os/restore-evidence}"
readonly server_name="${ZABBIX_SERVER_NAME:-ness.OS Zabbix}"

[[ -f ${server_config} && -f ${frontend_config} ]]

config_value() {
  local key=$1
  sed -n "s/^${key}=//p" "${server_config}" | tail -n 1
}

db_name="$(config_value DBName)"
db_user="$(config_value DBUser)"
db_password="$(config_value DBPassword)"

[[ ${db_name} =~ ^[A-Za-z0-9_]+$ ]]
[[ ${db_user} =~ ^[A-Za-z0-9_]+$ ]]
# Native restore generates this password with `openssl rand -hex 32`.
[[ ${db_password} =~ ^[0-9a-f]{64}$ ]]

install -d -o root -g root -m 0700 "${evidence_root}"
stamp="$(date +%Y%m%dT%H%M%S%z)"
backup="${evidence_root}/zabbix-web-config-before-sync-${stamp}.php"
install -o root -g root -m 0600 "${frontend_config}" "${backup}"

frontend_tmp="$(mktemp /etc/zabbix/web/.zabbix.conf.php.XXXXXX)"
trap 'rm -f -- "${frontend_tmp}"; unset db_password' EXIT

seen_database=0
seen_user=0
seen_password=0
seen_server_name=0
while IFS= read -r line; do
  case ${line} in
    *"\$DB['DATABASE']"*)
      printf "\$DB['DATABASE'] = '%s';\n" "${db_name}"
      seen_database=1
      ;;
    *"\$DB['USER']"*)
      printf "\$DB['USER'] = '%s';\n" "${db_user}"
      seen_user=1
      ;;
    *"\$DB['PASSWORD']"*)
      printf "\$DB['PASSWORD'] = '%s';\n" "${db_password}"
      seen_password=1
      ;;
    "\$ZBX_SERVER_NAME"*)
      printf "\$ZBX_SERVER_NAME = '%s';\n" "${server_name}"
      seen_server_name=1
      ;;
    *)
      printf '%s\n' "${line}"
      ;;
  esac
done <"${frontend_config}" >"${frontend_tmp}"

[[ ${seen_database} == 1 && ${seen_user} == 1 && ${seen_password} == 1 && ${seen_server_name} == 1 ]]
install -o root -g www-data -m 0640 "${frontend_tmp}" "${frontend_config}"

web_database="$(sed -n "s/^\$DB\['DATABASE'\][[:space:]]*=[[:space:]]*'\([^']*\)'.*/\1/p" "${frontend_config}" | tail -n 1)"
web_user="$(sed -n "s/^\$DB\['USER'\][[:space:]]*=[[:space:]]*'\([^']*\)'.*/\1/p" "${frontend_config}" | tail -n 1)"
web_password="$(sed -n "s/^\$DB\['PASSWORD'\][[:space:]]*=[[:space:]]*'\([^']*\)'.*/\1/p" "${frontend_config}" | tail -n 1)"
[[ ${web_database} == "${db_name}" ]]
[[ ${web_user} == "${db_user}" ]]
[[ ${web_password} == "${db_password}" ]]

unset db_password web_password
printf 'frontend_database=%s\n' "${db_name}"
printf 'frontend_user=%s\n' "${db_user}"
printf 'frontend_server_name=%s\n' "${server_name}"
printf 'frontend_sync=PASS\n'
