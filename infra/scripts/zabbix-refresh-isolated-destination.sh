#!/usr/bin/env bash
# Refresh the isolated migration database, preserving a completed rollback set.
set -Eeuo pipefail
umask 077
[[ ${EUID} == 0 ]] || { echo 'root required' >&2; exit 2; }
stage="${1:?STAGING_BACKUP_SET required}"
rollback="${2:?ROLLBACK_BACKUP_SET required}"
case "$(realpath "${stage}")" in /var/lib/ness-os/restore-input/*) ;; *) exit 2 ;; esac
case "$(realpath "${rollback}")" in /var/backups/zabbix/nightly/*) ;; *) exit 2 ;; esac
[[ -f ${stage}/COMPLETED && -f ${stage}/SHA256SUMS && -f ${rollback}/COMPLETED ]]
[[ "$(systemctl is-enabled zabbix-server 2>/dev/null || true)" == masked ]]
! systemctl is-active --quiet zabbix-server
! ss -H -lnt 'sport = :10051' | grep -q .
exec 9>/run/lock/ness-zabbix-backup.lock
flock -n 9 || { echo 'backup/refresh lock busy' >&2; exit 3; }
sha="$(awk '$2 ~ /\/db\/dbzabbix.sql.gz$/ {print $1}' "${stage}/SHA256SUMS")"
[[ ${sha} =~ ^[0-9a-f]{64}$ ]]
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "${here}/zabbix-kvm8-native-restore.sh" restore "${stage}/db/dbzabbix.sql.gz" "${sha}"
ZABBIX_SERVER_NAME='ness.os Zabbix UAT' bash "${here}/zabbix-sync-frontend-db.sh"
php -l /etc/zabbix/web/zabbix.conf.php >/dev/null
systemctl reload apache2
echo 'isolated_refresh=PASS'
