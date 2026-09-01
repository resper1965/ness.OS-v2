#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

install -m 0755 -o root -g root /tmp/restic /usr/local/bin/restic
install -d -m 0700 -o root -g root /etc/ness-os
install -m 0600 -o root -g root /tmp/backup-s3.env /etc/ness-os/backup-s3.env
sed -i 's/^NESS_BACKUP_HOST_ID=.*/NESS_BACKUP_HOST_ID=zbx-prd-01/' /etc/ness-os/backup-s3.env
install -m 0750 -o root -g root /tmp/ness-object-storage-restic.sh /usr/local/sbin/ness-object-storage-restic
install -m 0644 -o root -g root /tmp/ness-zabbix-object-storage-backup.service /etc/systemd/system/ness-zabbix-object-storage-backup.service
install -m 0644 -o root -g root /tmp/ness-zabbix-object-storage-backup.timer /etc/systemd/system/ness-zabbix-object-storage-backup.timer
systemctl daemon-reload
systemctl disable --now ness-zabbix-object-storage-backup.timer >/dev/null 2>&1 || true

restic version
stat -c '%a %U %G %n' /etc/ness-os/backup-s3.env
/usr/local/sbin/ness-object-storage-restic init zabbix
