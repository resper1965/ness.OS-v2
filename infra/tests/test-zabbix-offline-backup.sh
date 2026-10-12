#!/usr/bin/env bash
set -Eeuo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="${root}/infra/scripts/zabbix-offline-uat-backup.sh"
unit="${root}/infra/systemd/ness-zabbix-backup-offline-uat.service"
bash -n "${script}"
grep -Fq '== masked' "${script}"
grep -Fq "sport = :10051" "${script}"
grep -Fq 'Requires=' "${unit}"
grep -Fxq 'Requires=mariadb.service' "${unit}"
grep -Fxq 'ExecStart=/usr/local/sbin/ness-zabbix-offline-uat-backup' "${unit}"
if grep -Eq '^(Requires|Wants|ExecStart)=.*zabbix-server' "${unit}"; then
  echo 'offline backup must not activate collection' >&2; exit 1
fi
grep -Fq 'sha256sum -c' "${script}"
grep -Fq 'touch "${output}/COMPLETED"' "${script}"
echo 'zabbix offline backup contract: PASS'
