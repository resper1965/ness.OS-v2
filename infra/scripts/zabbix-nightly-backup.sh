#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

if [[ ${EUID} -ne 0 ]]; then
  echo "This backup must run as root." >&2
  exit 1
fi

readonly backup_root="/var/backups/zabbix/nightly"
readonly zabbix_config="/etc/zabbix/zabbix_server.conf"
readonly lock_file="/run/lock/ness-zabbix-backup.lock"
backup_stamp="$(date +%Y%m%dT%H%M%S%z)"
backup_dir="${backup_root}/${backup_stamp}"

case "${backup_dir}" in
  /var/backups/zabbix/nightly/*) ;;
  *) echo "Refusing unexpected backup path: ${backup_dir}" >&2; exit 90 ;;
esac

exec 9>"${lock_file}"
flock -n 9 || { echo "Another Zabbix backup is already running." >&2; exit 1; }

install -d -o root -g root -m 700 "${backup_root}"
available_kib="$(df --output=avail "${backup_root}" | tail -1 | tr -d ' ')"
if (( available_kib < 100 * 1024 * 1024 )); then
  echo "Less than 100 GiB available for the Zabbix backup." >&2
  exit 1
fi

systemctl is-active --quiet mariadb
systemctl is-active --quiet zabbix-server

db_user="$(sed -n 's/^DBUser=//p' "${zabbix_config}" | tail -1)"
db_password="$(sed -n 's/^DBPassword=//p' "${zabbix_config}" | tail -1)"
db_name="$(sed -n 's/^DBName=//p' "${zabbix_config}" | tail -1)"
db_user="${db_user:-zabbix}"
db_name="${db_name:-zabbix}"

install -d -m 700 "${backup_dir}/db" "${backup_dir}/config"
printf '%s\n' "${backup_dir}" > "${backup_root}/LATEST"
chmod 600 "${backup_root}/LATEST"

date --iso-8601=seconds > "${backup_dir}/CREATED_AT"
hostname > "${backup_dir}/HOSTNAME"
systemctl is-active mariadb zabbix-server apache2 zabbix-agent2 > "${backup_dir}/SERVICES_BEFORE"

export MYSQL_PWD="${db_password}"
nice -n 15 ionice -c2 -n7 mariadb-dump \
  --user="${db_user}" \
  --single-transaction \
  --quick \
  --routines \
  --events \
  --triggers \
  --hex-blob \
  --default-character-set=utf8mb4 \
  --databases "${db_name}" \
  | gzip -1 > "${backup_dir}/db/${db_name}.sql.gz"
unset MYSQL_PWD db_password

tar -C / -czf "${backup_dir}/config/zabbix-system-config.tar.gz" \
  etc/zabbix \
  etc/apache2 \
  etc/mysql \
  etc/letsencrypt \
  2>/dev/null

gzip -t "${backup_dir}/db/${db_name}.sql.gz"
systemctl is-active mariadb zabbix-server apache2 zabbix-agent2 > "${backup_dir}/SERVICES_AFTER"

find "${backup_dir}" -type f ! -name SHA256SUMS -print0 \
  | sort -z \
  | xargs -0 sha256sum > "${backup_dir}/SHA256SUMS"
sha256sum -c "${backup_dir}/SHA256SUMS"

chmod -R go-rwx "${backup_dir}"
touch "${backup_dir}/COMPLETED"
du -sh "${backup_dir}"
