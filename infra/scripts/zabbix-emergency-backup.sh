#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

if [[ ${EUID} -ne 0 ]]; then
  echo "This backup must run as root." >&2
  exit 1
fi

backup_stamp="$(date +%Y%m%dT%H%M%S%z)"
backup_root="/var/backups/zabbix/emergency"
backup_dir="${backup_root}/${backup_stamp}"
zabbix_config="/etc/zabbix/zabbix_server.conf"

case "${backup_dir}" in
  /var/backups/zabbix/emergency/*) ;;
  *) echo "Refusing unexpected backup path: ${backup_dir}" >&2; exit 90 ;;
esac

systemctl is-active --quiet mariadb
systemctl is-active --quiet zabbix-server

db_user="$(sed -n 's/^DBUser=//p' "${zabbix_config}" | tail -1)"
db_password="$(sed -n 's/^DBPassword=//p' "${zabbix_config}" | tail -1)"
db_name="$(sed -n 's/^DBName=//p' "${zabbix_config}" | tail -1)"

db_user="${db_user:-zabbix}"
db_name="${db_name:-zabbix}"

install -d -m 700 "${backup_dir}/db" "${backup_dir}/config" "${backup_dir}/evidence"
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

if [[ -d /root/incident-quarantine/20260820-zbx-sys-health ]]; then
  tar -C /root/incident-quarantine -czf \
    "${backup_dir}/evidence/20260820-zbx-sys-health.tar.gz" \
    20260820-zbx-sys-health
fi

gzip -t "${backup_dir}/db/${db_name}.sql.gz"
find "${backup_dir}" -type f ! -name SHA256SUMS -print0 \
  | sort -z \
  | xargs -0 sha256sum > "${backup_dir}/SHA256SUMS"
sha256sum -c "${backup_dir}/SHA256SUMS"
chmod -R go-rwx "${backup_dir}"

systemctl is-active mariadb zabbix-server apache2 zabbix-agent2 > "${backup_dir}/SERVICES_AFTER"
du -sh "${backup_dir}"
