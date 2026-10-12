#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly root=/var/backups/zabbix/nightly
readonly conf=/etc/zabbix/zabbix_server.conf
readonly lock=/run/lock/ness-zabbix-backup.lock
readonly stamp="$(date +%Y%m%dT%H%M%S%z)"
readonly output="${root}/${stamp}"

systemctl is-active --quiet mariadb
systemctl is-active --quiet zabbix-server && { echo 'refusing: Zabbix Server must remain offline for UAT backup' >&2; exit 1; }
[[ "$(systemctl is-enabled zabbix-server 2>/dev/null || true)" == masked ]] || {
  echo 'refusing: Zabbix Server must be masked for UAT backup' >&2; exit 1;
}
ss -H -lnt 'sport = :10051' | grep -q . && {
  echo 'refusing: collection listener 10051 exists' >&2; exit 1;
}

exec 9>"${lock}"
flock -n 9 || { echo 'another backup is active' >&2; exit 1; }
install -d -m 0700 -o root -g root "${output}/db" "${output}/config"

db_name="$(sed -n 's/^DBName=//p' "${conf}" | tail -1)"
db_user="$(sed -n 's/^DBUser=//p' "${conf}" | tail -1)"
db_password="$(sed -n 's/^DBPassword=//p' "${conf}" | tail -1)"
[[ -n "${db_name}" && -n "${db_user}" && -n "${db_password}" ]]

printf '%s\n' "${output}" >"${root}/LATEST"
date --iso-8601=seconds >"${output}/CREATED_AT"
printf '%s\n' 'offline-uat; zabbix-server=inactive-masked' >"${output}/MODE"
systemctl is-active mariadb zabbix-server apache2 zabbix-agent2 >"${output}/SERVICES_BEFORE" || true

export MYSQL_PWD="${db_password}"
nice -n 15 ionice -c2 -n7 mariadb-dump --user="${db_user}" --single-transaction --quick --routines --events --triggers --hex-blob --default-character-set=utf8mb4 --databases "${db_name}" | gzip -1 >"${output}/db/${db_name}.sql.gz"
unset MYSQL_PWD db_password

tar -C / -czf "${output}/config/zabbix-system-config.tar.gz" etc/zabbix etc/apache2 etc/mysql 2>/dev/null
gzip -t "${output}/db/${db_name}.sql.gz"
systemctl is-active mariadb zabbix-server apache2 zabbix-agent2 >"${output}/SERVICES_AFTER" || true
find "${output}" -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >"${output}/SHA256SUMS"
sha256sum -c "${output}/SHA256SUMS"
chmod -R go-rwx "${output}"
touch "${output}/COMPLETED"
printf 'offline-uat-backup=%s\n' "${output}"
