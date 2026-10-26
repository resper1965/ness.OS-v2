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
created_at_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

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

printf '%s\n' "${created_at_utc}" > "${backup_dir}/CREATED_AT"
backup_hostname="$(hostname)"
printf '%s\n' "${backup_hostname}" > "${backup_dir}/HOSTNAME"
systemctl is-active mariadb zabbix-server apache2 zabbix-agent2 > "${backup_dir}/SERVICES_BEFORE"

zabbix_version="$(zabbix_server -V | awk 'NR == 1 {print $3}')"
[[ "${zabbix_version}" == 7.0.27 ]] || {
  echo "expected Zabbix 7.0.27, found ${zabbix_version:-unknown}" >&2
  exit 1
}
[[ "${db_name}" =~ ^[A-Za-z0-9_]+$ ]] || {
  echo "unsafe database name in Zabbix configuration" >&2
  exit 1
}

db_metadata="$(MYSQL_PWD="${db_password}" mariadb --user="${db_user}" \
  --batch --skip-column-names "${db_name}" \
  -e 'SELECT VERSION(), mandatory FROM dbversion LIMIT 1')"
read -r server_mariadb_version dbversion_mandatory <<<"${db_metadata}"
mariadb_version="${server_mariadb_version%%-*}"
[[ "${mariadb_version}" =~ ^10\.11\.[0-9]+$ ]] || {
  echo "expected MariaDB 10.11.x, found ${mariadb_version:-unknown}" >&2
  exit 1
}
[[ "${dbversion_mandatory}" =~ ^[0-9]+$ ]] || {
  echo "could not read the Zabbix mandatory database version" >&2
  exit 1
}

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

python3 - "${backup_dir}/backup-set-manifest.json" "${backup_stamp}" \
  "${created_at_utc}" "${backup_hostname}" "${zabbix_version}" \
  "${mariadb_version}" "${db_name}" "${dbversion_mandatory}" <<'PY'
import json, sys
path, set_id, created, hostname, zabbix, mariadb, database, dbversion = sys.argv[1:]
manifest = {
    "backup_set_id": set_id,
    "created_at_utc": created,
    "hostname": hostname,
    "zabbix_version": zabbix,
    "mariadb_version": mariadb,
    "db_name": database,
    "dbversion_mandatory": int(dbversion),
}
with open(path, "w", encoding="utf-8") as output:
    json.dump(manifest, output, sort_keys=True)
    output.write("\n")
PY

required_artifacts=(
  "db/${db_name}.sql.gz"
  config/zabbix-system-config.tar.gz
  CREATED_AT
  HOSTNAME
  SERVICES_BEFORE
  SERVICES_AFTER
  backup-set-manifest.json
)
for artifact in "${required_artifacts[@]}"; do
  [[ -s "${backup_dir}/${artifact}" ]] || {
    echo "required Zabbix backup artifact missing or empty: ${artifact}" >&2
    exit 1
  }
done

(
  cd "${backup_dir}"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS
)
for artifact in "${required_artifacts[@]}"; do
  grep -Fq -- "./${artifact}" "${backup_dir}/SHA256SUMS" || {
    echo "required artifact is absent from the checksum manifest: ${artifact}" >&2
    exit 1
  }
done
(cd "${backup_dir}" && sha256sum -c SHA256SUMS)
tar -tzf "${backup_dir}/config/zabbix-system-config.tar.gz" >/dev/null

chmod -R go-rwx "${backup_dir}"
touch "${backup_dir}/COMPLETED"
printf '%s\n' "${backup_dir}" > "${backup_root}/.LATEST.$$"
chmod 600 "${backup_root}/.LATEST.$$"
mv -f -- "${backup_root}/.LATEST.$$" "${backup_root}/LATEST"
du -sh "${backup_dir}"
