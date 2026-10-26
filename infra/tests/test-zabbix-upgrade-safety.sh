#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
backup_script="${repo_root}/infra/scripts/zabbix-nightly-backup.sh"
restore_script="${repo_root}/infra/scripts/zabbix-isolated-restore-test.sh"
verify_script="${repo_root}/infra/scripts/verify-zabbix-restic-restore.sh"
restic_script="${repo_root}/infra/scripts/ness-object-storage-restic.sh"
timer_local="${repo_root}/infra/systemd/ness-zabbix-backup.timer"
timer_remote="${repo_root}/infra/systemd/ness-zabbix-object-storage-backup.timer"

bash -n "${backup_script}" "${restore_script}" "${verify_script}" "${restic_script}"
grep -Fq 'backup-set-manifest.json' "${backup_script}"
grep -Fq 'zabbix_version' "${backup_script}"
grep -Fq 'mariadb_version' "${backup_script}"
grep -Fq 'dbversion_mandatory' "${backup_script}"
grep -Fq 'backup_set_id' "${verify_script}"
grep -Fq -- '--verify' "${verify_script}"
grep -Fq -- '--tag "${set_tag}"' "${restic_script}"
grep -Fq 'ness-backup-set-' "${restic_script}"
grep -Fq -- '--validate-set' "${restore_script}"
grep -Fq '/var/backups/zabbix/nightly/*' "${restore_script}"
grep -Fq 'run-${run_id}-XXXXXX' "${restore_script}"
grep -Fq 'chmod 0710 "${restore_root}"' "${restore_script}"
grep -Fq '10.11' "${restore_script}"
grep -Fq -- '--skip-networking' "${restore_script}"
if grep -Fq 'docker run' "${restore_script}"; then
  echo 'isolated MariaDB validation must not depend on Docker on the Zabbix VPS' >&2
  exit 1
fi
grep -Fq "OnCalendar=*-*-* 22:00:00 America/Sao_Paulo" "${timer_local}"
grep -Fq "OnCalendar=*-*-* 05:30:00 America/Sao_Paulo" "${timer_remote}"
grep -Fq 'AccuracySec=1min' "${timer_remote}"

command -v python3 >/dev/null || { echo 'python3 is required' >&2; exit 1; }
tmp="$(mktemp -d)"
trap 'rm -rf -- "${tmp}"' EXIT
set_id=20260925T120000-0300
valid="${tmp}/${set_id}"
mkdir -p "${valid}/db" "${valid}/config"
printf 'CREATE DATABASE dbzabbix;\n' | gzip -c >"${valid}/db/dbzabbix.sql.gz"
printf 'fixture configuration\n' >"${tmp}/zabbix_server.conf"
tar -czf "${valid}/config/zabbix-system-config.tar.gz" -C "${tmp}" zabbix_server.conf
printf '2026-09-25T15:20:00Z\n' >"${valid}/CREATED_AT"
printf 'fixture-host\n' >"${valid}/HOSTNAME"
printf 'active\n' >"${valid}/SERVICES_BEFORE"
printf 'active\n' >"${valid}/SERVICES_AFTER"
printf '{"backup_set_id":"%s","created_at_utc":"2026-09-25T15:20:00Z","hostname":"fixture-host","zabbix_version":"7.0.27","mariadb_version":"10.11.18","db_name":"dbzabbix","dbversion_mandatory":7000000}\n' \
  "${set_id}" >"${valid}/backup-set-manifest.json"
(
  cd "${valid}"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS
)
touch "${valid}/COMPLETED"
output="$(bash "${restore_script}" --validate-set "${valid}")"
grep -Fq "backup_set_id=${set_id}" <<<"${output}"
grep -Fq 'zabbix_version=7.0.27' <<<"${output}"

partial="${tmp}/partial"
cp -a "${valid}" "${partial}"
rm -f "${partial}/COMPLETED"
if bash "${restore_script}" --validate-set "${partial}" >/dev/null 2>&1; then
  echo 'partial Zabbix backup set was accepted' >&2
  exit 1
fi

corrupt="${tmp}/corrupt"
cp -a "${valid}" "${corrupt}"
printf 'tampered\n' >>"${corrupt}/db/dbzabbix.sql.gz"
if bash "${restore_script}" --validate-set "${corrupt}" >/dev/null 2>&1; then
  echo 'Zabbix backup with mismatched checksum was accepted' >&2
  exit 1
fi

wrong_version="${tmp}/wrong-version"
cp -a "${valid}" "${wrong_version}"
sed -i 's/"zabbix_version":"7.0.27"/"zabbix_version":"7.0.28"/' \
  "${wrong_version}/backup-set-manifest.json"
(
  cd "${wrong_version}"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS
)
if bash "${restore_script}" --validate-set "${wrong_version}" >/dev/null 2>&1; then
  echo 'backup from an incompatible Zabbix version was accepted' >&2
  exit 1
fi

echo 'zabbix upgrade safety and recovery checks: PASS'
