#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
readonly INPUT_ROOT="/var/lib/ness-os/restore-input"
readonly SCHEMA="/usr/share/zabbix-sql-scripts/mysql/server.sql.gz"
readonly DUMP="${INPUT_ROOT}/synthetic-zabbix-7.0.27.sql.gz"

if [[ ${EUID} -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

systemctl is-active --quiet mariadb
[[ "$(systemctl is-enabled zabbix-server 2>/dev/null || true)" == masked ]]
[[ -f ${SCHEMA} ]]
install -d -m 0700 "${INPUT_ROOT}"

mariadb --protocol=socket --execute='DROP DATABASE IF EXISTS `dbzabbix`; CREATE DATABASE `dbzabbix` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;'
gzip -dc "${SCHEMA}" | mariadb --protocol=socket --binary-mode dbzabbix
mariadb-dump --protocol=socket --single-transaction --quick --routines --events --triggers --hex-blob --databases dbzabbix \
  | gzip -1 > "${DUMP}"
mariadb --protocol=socket --execute='DROP DATABASE `dbzabbix`;'

dump_sha="$(sha256sum "${DUMP}" | awk '{print $1}')"
/usr/local/sbin/ness-zabbix-kvm8-native-restore restore "${DUMP}" "${dump_sha}"
