#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
mariadb_image='mariadb:10.11@sha256:be981e4113326ada8d6004174dd09eeaefc03094037f811182a52d4f2e737350a'

validate_backup_set() {
  backup_dir="$(realpath -e "${1:?backup set directory required}")"
  [[ -d "${backup_dir}" && -f "${backup_dir}/COMPLETED" ]] || {
    echo 'Zabbix backup set is incomplete: COMPLETED is missing' >&2
    return 1
  }
  [[ -s "${backup_dir}/SHA256SUMS" && -s "${backup_dir}/backup-set-manifest.json" ]] || {
    echo 'Zabbix backup set lacks its checksum or manifest' >&2
    return 1
  }

  local metadata
  metadata="$(python3 - "${backup_dir}/backup-set-manifest.json" <<'PY'
import json, re, sys
with open(sys.argv[1], encoding="utf-8") as source:
    value = json.load(source)
required = (
    "backup_set_id", "created_at_utc", "hostname", "zabbix_version",
    "mariadb_version", "db_name", "dbversion_mandatory",
)
assert all(key in value for key in required), "manifest is incomplete"
assert re.fullmatch(r"[0-9]{8}T[0-9]{6}-[0-9]{4}", value["backup_set_id"]), "invalid backup_set_id"
assert re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value["created_at_utc"]), "invalid UTC timestamp"
assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", value["hostname"]), "invalid hostname"
assert value["zabbix_version"] == "7.0.27", "backup is not from Zabbix 7.0.27"
assert re.fullmatch(r"10\.11\.[0-9]+", value["mariadb_version"]), "backup is not from MariaDB 10.11"
assert re.fullmatch(r"[A-Za-z0-9_]+", value["db_name"]), "invalid database name"
assert isinstance(value["dbversion_mandatory"], int) and value["dbversion_mandatory"] > 0, "invalid mandatory DB version"
print("\t".join(str(value[key]) for key in required))
PY
)" || return 1

  IFS=$'\t' read -r backup_set_id created_at_utc backup_hostname zabbix_version \
    mariadb_version db_name dbversion_mandatory <<<"${metadata}"
  [[ "${backup_set_id}" == "$(basename "${backup_dir}")" ]] || {
    echo 'manifest backup_set_id does not match the set directory' >&2
    return 1
  }

  local -a required_artifacts=(
    "db/${db_name}.sql.gz"
    config/zabbix-system-config.tar.gz
    CREATED_AT HOSTNAME SERVICES_BEFORE SERVICES_AFTER backup-set-manifest.json
  )
  for artifact in "${required_artifacts[@]}"; do
    [[ -s "${backup_dir}/${artifact}" ]] || {
      echo "required Zabbix backup artifact missing or empty: ${artifact}" >&2
      return 1
    }
    grep -Fq -- "./${artifact}" "${backup_dir}/SHA256SUMS" || {
      echo "required artifact is absent from SHA256SUMS: ${artifact}" >&2
      return 1
    }
  done
  (cd "${backup_dir}" && sha256sum -c SHA256SUMS >/dev/null)
  gzip -t "${backup_dir}/db/${db_name}.sql.gz"
  tar -tzf "${backup_dir}/config/zabbix-system-config.tar.gz" >/dev/null
}

if [[ "${1:-}" == --validate-set ]]; then
  [[ $# -eq 2 ]] || { echo "usage: $0 --validate-set BACKUP_SET" >&2; exit 2; }
  validate_backup_set "$2"
  echo "zabbix_backup_set=PASS backup_set_id=${backup_set_id} zabbix_version=${zabbix_version} mariadb_version=${mariadb_version} dbversion_mandatory=${dbversion_mandatory}"
  exit 0
fi

[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }
backup_dir="${1:?completed backup set directory required}"
resolved_input="$(realpath -e "${backup_dir}")"
case "${resolved_input}" in
  /var/lib/ness-os/restic-restore-verify/*|/opt/n-infraops/restore-input/*|/var/backups/zabbix/nightly/*) ;;
  *) echo 'restore input is outside its approved temporary roots' >&2; exit 2 ;;
esac
validate_backup_set "${resolved_input}"

for command in mariadb mariadb-admin mariadb-install-db mariadbd openssl; do
  command -v "${command}" >/dev/null || { echo "missing command: ${command}" >&2; exit 1; }
done

run_id="$(date +%Y%m%dT%H%M%S%z | tr '[:upper:]' '[:lower:]')-$$"
restore_root=/var/lib/ness-os/zabbix-restore-tests
install -d -o root -g mysql -m 0710 "${restore_root}"
chown root:mysql "${restore_root}"
chmod 0710 "${restore_root}"
work="$(mktemp -d "${restore_root}/run-${run_id}-XXXXXX")"
chown mysql:mysql "${work}"
chmod 700 "${work}"
datadir="${work}/data"
socket="${work}/mariadb.sock"
pidfile="${work}/mariadb.pid"
logfile="${work}/mariadb.log"
root_password="$(openssl rand -hex 32)"
server_pid=""
password_set=0

cleanup() {
  if [[ -S "${socket}" ]]; then
    if (( password_set )); then
      MYSQL_PWD="${root_password}" mariadb-admin --no-defaults --socket="${socket}" -uroot shutdown >/dev/null 2>&1 || true
    else
      mariadb-admin --no-defaults --socket="${socket}" -uroot shutdown >/dev/null 2>&1 || true
    fi
  fi
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill -TERM "${server_pid}" 2>/dev/null || true
  fi
  if [[ -n "${server_pid}" ]]; then
    wait "${server_pid}" 2>/dev/null || true
  fi
  case "$(realpath -m "${work}")" in
    "${restore_root}"/run-*) rm -rf -- "${work}" ;;
    *) echo 'refusing to remove an unexpected restore directory' >&2 ;;
  esac
}
trap cleanup EXIT

mariadb-install-db --user=mysql --datadir="${datadir}" \
  --auth-root-authentication-method=normal --skip-test-db >/dev/null
mariadbd --no-defaults --user=mysql --datadir="${datadir}" \
  --socket="${socket}" --pid-file="${pidfile}" \
  --skip-networking --log-error="${logfile}" \
  --innodb-buffer-pool-size=2G --max-allowed-packet=1G \
  >"${work}/mariadbd.stdout" 2>&1 &
server_pid=$!

for _ in $(seq 1 90); do
  if mariadb-admin --no-defaults --socket="${socket}" -uroot ping --silent >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
mariadb-admin --no-defaults --socket="${socket}" -uroot ping --silent >/dev/null
mariadb --no-defaults --socket="${socket}" -uroot \
  -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '${root_password}'"
password_set=1

db_name="$(python3 - "${backup_dir}/backup-set-manifest.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as source:
    print(json.load(source)["db_name"])
PY
)"
dump="${backup_dir}/db/${db_name}.sql.gz"
gzip -dc "${dump}" \
  | MYSQL_PWD="${root_password}" mariadb --no-defaults --socket="${socket}" \
      -uroot --max-allowed-packet=1G

query() {
  MYSQL_PWD="${root_password}" mariadb --no-defaults --socket="${socket}" \
    -uroot --batch --skip-column-names -e "${1}"
}

restored_mariadb_version="$(query 'SELECT VERSION();')"
[[ "${restored_mariadb_version}" == 10.11.* ]] || {
  echo "restored MariaDB is incompatible with production 10.11: ${restored_mariadb_version}" >&2
  exit 5
}
tables="$(query "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${db_name}';")"
hosts="$(query "SELECT COUNT(*) FROM \`${db_name}\`.hosts;")"
items="$(query "SELECT COUNT(*) FROM \`${db_name}\`.items;")"
triggers="$(query "SELECT COUNT(*) FROM \`${db_name}\`.triggers;")"
templates="$(query "SELECT COUNT(*) FROM \`${db_name}\`.hosts WHERE status=3;")"
dbversion="$(query "SELECT mandatory FROM \`${db_name}\`.dbversion LIMIT 1;")"

[[ "${tables}" =~ ^[0-9]+$ && "${tables}" -gt 100 ]]
[[ "${hosts}" =~ ^[0-9]+$ && "${hosts}" -gt 0 ]]
[[ "${items}" =~ ^[0-9]+$ && "${items}" -gt 0 ]]
[[ "${triggers}" =~ ^[0-9]+$ && "${triggers}" -gt 0 ]]
[[ "${templates}" =~ ^[0-9]+$ && "${templates}" -gt 0 ]]
[[ "${dbversion}" == "${dbversion_mandatory}" ]]

printf 'zabbix_version=%s\n' "${zabbix_version}"
printf 'mariadb_version=%s\n' "${restored_mariadb_version}"
printf 'zabbix_tables=%s\n' "${tables}"
printf 'zabbix_hosts=%s\n' "${hosts}"
printf 'zabbix_items=%s\n' "${items}"
printf 'zabbix_triggers=%s\n' "${triggers}"
printf 'zabbix_templates=%s\n' "${templates}"
printf 'zabbix_dbversion_mandatory=%s\n' "${dbversion}"
echo "isolated_restore=PASS backup_set_id=${backup_set_id}"
