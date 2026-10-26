#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly gate_epoch="$(date -d '2026-08-30T17:59:56-03:00' +%s)"
readonly backup_command=/usr/local/sbin/ness-zabbix-offline-cutover-backup
readonly zabbix_config=/etc/zabbix/zabbix_server.conf
readonly evidence_root=/var/backups/zabbix/cutover

(( $(date +%s) >= gate_epoch )) || { echo 'pilot gate has not completed 24 hours' >&2; exit 2; }
[[ -x ${backup_command} ]]
systemctl is-active --quiet mariadb zabbix-server
[[ "$(systemctl --failed --no-legend | wc -l)" == 0 ]]

install -d -m 0700 -o root -g root "${evidence_root}"
stamp="$(date +%Y%m%dT%H%M%S%z)"
before="${evidence_root}/source-freeze-before-${stamp}.tsv"
result="${evidence_root}/source-freeze-result-${stamp}.txt"

db_name="$(sed -n 's/^DBName=//p' "${zabbix_config}" | tail -1)"
db_user="$(sed -n 's/^DBUser=//p' "${zabbix_config}" | tail -1)"
db_password="$(sed -n 's/^DBPassword=//p' "${zabbix_config}" | tail -1)"
[[ -n ${db_name} && -n ${db_user} && -n ${db_password} ]]
export MYSQL_PWD="${db_password}"

{
  printf 'section\tid\tname\tstatus\n'
  mysql --batch --raw --skip-column-names --user="${db_user}" "${db_name}" \
    -e "SELECT 'host',hostid,host,status FROM hosts WHERE hostid IN (10873,10874) ORDER BY hostid;"
  mysql --batch --raw --skip-column-names --user="${db_user}" "${db_name}" \
    -e "SELECT 'action',actionid,name,status FROM actions WHERE status=0 ORDER BY actionid;"
  mysql --batch --raw --skip-column-names --user="${db_user}" "${db_name}" \
    -e "SELECT 'media',mediatypeid,name,status FROM media_type WHERE status=0 ORDER BY mediatypeid;"
} >"${before}"
chmod 0600 "${before}"

systemctl disable --now ness-zabbix-backup.timer ness-zabbix-object-storage-backup.timer
systemctl stop zabbix-server
! systemctl is-active --quiet zabbix-server
! pgrep -x zabbix_server >/dev/null
! ss -H -lnt 'sport = :10051' | grep -q .

mysql --user="${db_user}" "${db_name}" \
  -e "UPDATE hosts SET status=0 WHERE hostid IN (10873,10874);"
[[ "$(mysql --batch --raw --skip-column-names --user="${db_user}" "${db_name}" -e "SELECT SUM(status=0) FROM hosts WHERE hostid IN (10873,10874);")" == 2 ]]

"${backup_command}"

latest="$(cat /var/backups/zabbix/nightly/LATEST)"
case ${latest} in
  /var/backups/zabbix/nightly/*) ;;
  *) echo 'unexpected final backup path' >&2; exit 3 ;;
esac
[[ -e ${latest}/COMPLETED ]]
gzip -t "${latest}/db/${db_name}.sql.gz"
sha256sum -c "${latest}/SHA256SUMS" >/dev/null
dump_sha="$(sha256sum "${latest}/db/${db_name}.sql.gz" | awk '{print $1}')"

{
  printf 'frozen_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'source_zabbix_state=%s\n' "$(systemctl is-active zabbix-server 2>/dev/null || true)"
  printf 'source_zabbix_enabled=%s\n' "$(systemctl is-enabled zabbix-server 2>/dev/null || true)"
  printf 'pilot_hosts_enabled_in_dump=2\n'
  printf 'backup_set=%s\n' "${latest}"
  printf 'dump=%s\n' "${latest}/db/${db_name}.sql.gz"
  printf 'dump_sha256=%s\n' "${dump_sha}"
  printf 'gzip=PASS\n'
  printf 'manifest=PASS\n'
  printf 'source_freeze_backup=PASS\n'
} >"${result}"
chmod 0600 "${result}"
cat "${result}"

unset db_password MYSQL_PWD
