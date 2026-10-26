#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
readonly EVIDENCE_ROOT="/var/lib/ness-os/restore-evidence"
readonly DB_NAME="dbzabbix"
readonly ISOLATION_DROPIN="/etc/systemd/system/zabbix-server.service.d/10-staging-isolation.conf"

if [[ ${EUID} -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

started="$(date +%s)"
checked_at="$(date --iso-8601=seconds)"
failed_check="initialization"
source_evidence_sha256="unknown"
verification_basis="unknown"
mariadb_state="unknown"
mariadb_bind="unknown"
zabbix_state="unknown"
zabbix_enabled="unknown"
apache_state="unknown"
agent_state="unknown"
ntp_synchronized="unknown"
tables="unknown"
hosts="unknown"
items="unknown"
triggers="unknown"
dbversion="unknown"
active_actions="unknown"
enabled_media="unknown"
enabled_connectors="unknown"
disk_available_kb="unknown"
report=""
written=0

write_report() {
  local result="$1" finished elapsed
  (( written == 0 )) || return 0
  finished="$(date +%s)"
  elapsed="$((finished - started))"
  report="${EVIDENCE_ROOT}/post-restore-verification-$(date +%Y%m%dT%H%M%S%z).txt"
  {
    printf 'checked_at=%s\n' "${checked_at}"
    printf 'elapsed_seconds=%s\n' "${elapsed}"
    printf 'source_evidence_sha256=%s\n' "${source_evidence_sha256}"
    printf 'verification_basis=%s\n' "${verification_basis}"
    printf 'mariadb_state=%s\n' "${mariadb_state}"
    printf 'mariadb_bind=%s\n' "${mariadb_bind}"
    printf 'zabbix_server_state=%s\n' "${zabbix_state}"
    printf 'zabbix_server_enabled=%s\n' "${zabbix_enabled}"
    printf 'apache_state=%s\n' "${apache_state}"
    printf 'agent_state=%s\n' "${agent_state}"
    printf 'ntp_synchronized=%s\n' "${ntp_synchronized}"
    printf 'tables=%s\n' "${tables}"
    printf 'hosts=%s\n' "${hosts}"
    printf 'items=%s\n' "${items}"
    printf 'triggers=%s\n' "${triggers}"
    printf 'dbversion_mandatory=%s\n' "${dbversion}"
    printf 'active_actions=%s\n' "${active_actions}"
    printf 'enabled_media=%s\n' "${enabled_media}"
    printf 'enabled_connectors=%s\n' "${enabled_connectors}"
    printf 'disk_available_kb=%s\n' "${disk_available_kb}"
    printf 'failed_check=%s\n' "${failed_check}"
    printf 'post_restore_verification=%s\n' "${result}"
  } >"${report}"
  chmod 0600 "${report}"
  written=1
}

fail() {
  failed_check="$1"
  write_report FAIL
  echo "post-restore verification: FAIL (${failed_check})" >&2
  exit 1
}

[[ -d ${EVIDENCE_ROOT} ]] || { echo "evidence directory is absent" >&2; exit 1; }

mariadb_state="$(systemctl is-active mariadb 2>/dev/null || true)"
[[ ${mariadb_state} == active ]] || fail mariadb_active

mapfile -t mariadb_listeners < <(ss -H -lnt 'sport = :3306')
(( ${#mariadb_listeners[@]} > 0 )) || fail mariadb_listener
for listener in "${mariadb_listeners[@]}"; do
  local_address="$(awk '{print $4}' <<<"${listener}")"
  [[ ${local_address} =~ ^(127\.0\.0\.1|\[::1\]|::1):3306$ ]] || fail mariadb_not_localhost_only
done
mariadb_bind="localhost-only"

zabbix_state="$(systemctl is-active zabbix-server 2>/dev/null || true)"
zabbix_enabled="$(systemctl is-enabled zabbix-server 2>/dev/null || true)"
[[ ${zabbix_state} == inactive ]] || fail zabbix_server_not_inactive
[[ ${zabbix_enabled} == masked ]] || fail zabbix_server_not_masked
pgrep -x zabbix_server >/dev/null && fail zabbix_server_process_present
ss -H -lnt 'sport = :10051' | grep -q . && fail zabbix_listener_present

apache_state="$(systemctl is-active apache2 2>/dev/null || true)"
agent_state="$(systemctl is-active zabbix-agent2 2>/dev/null || true)"
[[ ${apache_state} != active ]] || fail apache_active
[[ ${agent_state} != active ]] || fail agent_active

[[ -f ${ISOLATION_DROPIN} ]] || fail isolation_dropin_absent
grep -Eq '^[[:space:]]*IPAddressDeny=any[[:space:]]*$' "${ISOLATION_DROPIN}" || fail ip_address_deny_absent
grep -Eq '^[[:space:]]*IPAddressAllow=localhost[[:space:]]*$' "${ISOLATION_DROPIN}" || fail ip_address_allow_absent

ntp_synchronized="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || true)"
[[ ${ntp_synchronized} == yes ]] || fail ntp_not_synchronized

latest_evidence="$(find "${EVIDENCE_ROOT}" -maxdepth 1 -type f -name 'restore-[0-9]*.txt' \
  -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
[[ -n ${latest_evidence} ]] || fail restore_evidence_absent
[[ "$(stat -c '%u:%a' "${latest_evidence}")" == 0:600 ]] || fail restore_evidence_not_root_only
source_evidence_sha256="$(sha256sum "${latest_evidence}" | awk '{print $1}')"

evidence_value() {
  awk -F= -v key="$1" '$1 == key { print $2; exit }' "${latest_evidence}"
}

if [[ -s ${latest_evidence} ]] && grep -qx 'restore=PASS' "${latest_evidence}"; then
  verification_basis="restore-pass-evidence"
  tables="$(evidence_value tables)"
  hosts="$(evidence_value hosts)"
  items="$(evidence_value items)"
  triggers="$(evidence_value triggers)"
else
  verification_basis="database-direct-after-fail-closed"
  tables="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}';" 2>/dev/null)" || fail tables_query
  hosts="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.hosts;" 2>/dev/null)" || fail hosts_query
  items="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.items;" 2>/dev/null)" || fail items_query
  triggers="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.triggers;" 2>/dev/null)" || fail triggers_query
fi
for value in "${tables}" "${hosts}" "${items}" "${triggers}"; do
  [[ ${value} =~ ^[0-9]+$ ]] || fail invalid_evidence_count
done
(( tables > 100 && hosts > 0 && items > 0 && triggers > 0 )) || fail invalid_evidence_count

required_tables="$(mariadb --protocol=socket -NBe \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}' AND table_name IN ('dbversion','hosts','items','triggers','actions','media_type');" 2>/dev/null)" || fail required_table_query
[[ ${required_tables} == 6 ]] || fail required_tables_absent

dbversion="$(mariadb --protocol=socket -NBe "SELECT mandatory FROM ${DB_NAME}.dbversion LIMIT 1;" 2>/dev/null)" || fail dbversion_query
[[ ${dbversion} == 7000000 ]] || fail invalid_dbversion
active_actions="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.actions WHERE status=0;" 2>/dev/null)" || fail actions_query
enabled_media="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.media_type WHERE status=0;" 2>/dev/null)" || fail media_query
connector_exists="$(mariadb --protocol=socket -NBe \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}' AND table_name='connector';" 2>/dev/null)" || fail connector_table_query
enabled_connectors=0
if [[ ${connector_exists} == 1 ]]; then
  enabled_connectors="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.connector WHERE status=0;" 2>/dev/null)" || fail connectors_query
fi
for value in "${active_actions}" "${enabled_media}" "${enabled_connectors}"; do
  [[ ${value} =~ ^[0-9]+$ ]] || fail invalid_integration_count
done
[[ ${active_actions} == 0 ]] || fail active_actions_present
[[ ${enabled_media} == 0 ]] || fail enabled_media_present
[[ ${enabled_connectors} == 0 ]] || fail enabled_connectors_present

disk_available_kb="$(df -Pk "${EVIDENCE_ROOT}" | awk 'NR == 2 {print $4}')"
[[ ${disk_available_kb} =~ ^[0-9]+$ ]] || fail disk_check

failed_check="none"
write_report PASS
echo "post-restore verification: PASS"
