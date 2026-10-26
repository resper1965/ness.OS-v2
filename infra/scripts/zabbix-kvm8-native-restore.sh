#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
readonly INPUT_ROOT="/var/lib/ness-os/restore-input"
readonly EVIDENCE_ROOT="/var/lib/ness-os/restore-evidence"
readonly DB_NAME="dbzabbix"

assert_zabbix_isolated() {
  if systemctl is-active --quiet zabbix-server; then
    echo "refusing restore while zabbix-server service is active" >&2
    return 1
  fi
  [[ "$(systemctl is-enabled zabbix-server 2>/dev/null || true)" == masked ]]
  if pgrep -x zabbix_server >/dev/null; then
    echo "refusing restore while a zabbix_server process exists" >&2
    return 1
  fi
  if ss -H -lnt 'sport = :10051' | grep -q .; then
    echo "refusing restore while TCP port 10051 is listening" >&2
    return 1
  fi
}

fail_closed() {
  local exit_code=$?
  trap - ERR
  set +e
  systemctl stop zabbix-server >/dev/null 2>&1
  pkill -TERM -x zabbix_server >/dev/null 2>&1
  if mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='${DB_NAME}';" | grep -qx 1; then
    mariadb --protocol=socket --execute="UPDATE ${DB_NAME}.actions SET status=1 WHERE status=0;" >/dev/null 2>&1
    mariadb --protocol=socket --execute="UPDATE ${DB_NAME}.media_type SET status=1 WHERE status=0;" >/dev/null 2>&1
    if mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}' AND table_name='connector';" | grep -qx 1; then
      mariadb --protocol=socket --execute="UPDATE ${DB_NAME}.connector SET status=1 WHERE status=0;" >/dev/null 2>&1
    fi
  fi
  local failure_evidence="${EVIDENCE_ROOT}/restore-failed-$(date +%Y%m%dT%H%M%S%z).txt"
  {
    printf 'exit_code=%s\n' "${exit_code}"
    printf 'zabbix_server_state=%s\n' "$(systemctl is-active zabbix-server 2>/dev/null || true)"
    printf 'zabbix_server_enabled=%s\n' "$(systemctl is-enabled zabbix-server 2>/dev/null || true)"
    printf 'restore=FAIL_CLOSED\n'
  } >"${failure_evidence}"
  chmod 0600 "${failure_evidence}"
  exit "${exit_code}"
}

if [[ ${EUID} -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

prepare() {
  install -d -m 0700 "${INPUT_ROOT}" "${EVIDENCE_ROOT}"
  install -m 0644 /dev/stdin /etc/mysql/mariadb.conf.d/99-zabbix-transmutation.cnf <<'EOF'
[mariadb]
bind-address = 127.0.0.1
skip-name-resolve
max_allowed_packet = 1G
innodb_buffer_pool_size = 16G
innodb_log_file_size = 2G
innodb_log_buffer_size = 256M
innodb_flush_method = O_DIRECT
innodb_flush_log_at_trx_commit = 1
log_bin_trust_function_creators = 1
character_set_server = utf8mb4
collation_server = utf8mb4_bin
EOF
  systemctl restart mariadb
  systemctl mask zabbix-server
  systemctl disable --now zabbix-agent2 apache2 >/dev/null 2>&1 || true
  install -d -m 0755 /etc/systemd/system/zabbix-server.service.d
  install -m 0644 /dev/stdin /etc/systemd/system/zabbix-server.service.d/10-staging-isolation.conf <<'EOF'
[Service]
IPAddressDeny=any
IPAddressAllow=localhost
NoNewPrivileges=true
PrivateTmp=true
EOF
  systemctl daemon-reload
}

restore_dump() {
  local input_file="${1:-}"
  local expected_sha="${2:-}"
  [[ -n ${input_file} && -f ${input_file} ]]
  [[ ${expected_sha} =~ ^[0-9a-f]{64}$ ]]

  local resolved_input
  resolved_input="$(realpath "${input_file}")"
  case "${resolved_input}" in
    "${INPUT_ROOT}"/*) ;;
    *) echo "input must be below ${INPUT_ROOT}" >&2; exit 2 ;;
  esac

  systemctl is-active --quiet mariadb
  assert_zabbix_isolated

  local actual_sha
  actual_sha="$(sha256sum "${resolved_input}" | awk '{print $1}')"
  [[ ${actual_sha} == "${expected_sha}" ]]
  gzip -t "${resolved_input}"

  local started finished elapsed evidence_file db_password
  trap fail_closed ERR
  started="$(date +%s)"
  mariadb --protocol=socket --execute="DROP DATABASE IF EXISTS \`${DB_NAME}\`;"
  gzip -dc "${resolved_input}" | mariadb --protocol=socket --binary-mode --max-allowed-packet=1G

  local active_actions_before enabled_media_before enabled_connectors_before
  active_actions_before="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.actions WHERE status=0;")"
  enabled_media_before="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.media_type WHERE status=0;")"
  enabled_connectors_before=0
  if [[ "$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}' AND table_name='connector';")" == 1 ]]; then
    enabled_connectors_before="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.connector WHERE status=0;")"
    mariadb --protocol=socket --execute="UPDATE ${DB_NAME}.connector SET status=1 WHERE status=0;"
  fi
  mariadb --protocol=socket --execute="UPDATE ${DB_NAME}.actions SET status=1 WHERE status=0; UPDATE ${DB_NAME}.media_type SET status=1 WHERE status=0;"

  db_password="$(openssl rand -hex 32)"
  mariadb --protocol=socket <<SQL
DROP USER IF EXISTS 'zabbix_staging'@'localhost';
CREATE USER 'zabbix_staging'@'localhost' IDENTIFIED BY '${db_password}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO 'zabbix_staging'@'localhost';
FLUSH PRIVILEGES;
SQL

  if [[ ! -e /etc/zabbix/zabbix_server.conf.package-default ]]; then
    cp --preserve=all /etc/zabbix/zabbix_server.conf /etc/zabbix/zabbix_server.conf.package-default
  fi
  install -o root -g zabbix -m 0640 /dev/stdin /etc/zabbix/zabbix_server.conf <<EOF
LogFile=/var/log/zabbix/zabbix_server.log
PidFile=/run/zabbix/zabbix_server.pid
SocketDir=/run/zabbix
DBHost=localhost
DBName=${DB_NAME}
DBUser=zabbix_staging
DBPassword=${db_password}
ListenIP=127.0.0.1
ListenPort=10051
StartPollers=1
StartTrappers=1
StartPingers=1
StartDiscoverers=1
StartHTTPPollers=1
CacheSize=512M
ValueCacheSize=512M
HistoryCacheSize=256M
TrendCacheSize=128M
Timeout=10
LogSlowQueries=3000
EnableGlobalScripts=0
EOF

  /usr/local/sbin/ness-zabbix-sync-frontend-db
  unset db_password

  local tables hosts items triggers dbversion active_actions_after enabled_media_after enabled_connectors_after
  tables="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}';")"
  hosts="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.hosts;")"
  items="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.items;")"
  triggers="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.triggers;")"
  dbversion="$(mariadb --protocol=socket -NBe "SELECT mandatory FROM ${DB_NAME}.dbversion LIMIT 1;")"
  active_actions_after="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.actions WHERE status=0;")"
  enabled_media_after="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.media_type WHERE status=0;")"
  enabled_connectors_after=0
  if [[ "$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}' AND table_name='connector';")" == 1 ]]; then
    enabled_connectors_after="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${DB_NAME}.connector WHERE status=0;")"
  fi

  for value in "${tables}" "${hosts}" "${items}" "${triggers}" "${dbversion}" \
    "${active_actions_after}" "${enabled_media_after}" "${enabled_connectors_after}"; do
    [[ ${value} =~ ^[0-9]+$ ]]
  done
  (( tables > 100 ))
  (( hosts > 0 ))
  (( items > 0 ))
  (( triggers > 0 ))
  [[ ${dbversion} == 7000000 ]]
  [[ ${active_actions_after} == 0 ]]
  [[ ${enabled_media_after} == 0 ]]
  [[ ${enabled_connectors_after} == 0 ]]
  assert_zabbix_isolated

  finished="$(date +%s)"
  elapsed="$((finished - started))"
  evidence_file="${EVIDENCE_ROOT}/restore-$(date +%Y%m%dT%H%M%S%z).txt"
  local evidence_tmp="${evidence_file}.tmp"
  {
    printf 'input_sha256=%s\n' "${actual_sha}"
    printf 'restore_elapsed_seconds=%s\n' "${elapsed}"
    printf 'tables=%s\n' "${tables}"
    printf 'hosts=%s\n' "${hosts}"
    printf 'items=%s\n' "${items}"
    printf 'triggers=%s\n' "${triggers}"
    printf 'dbversion_mandatory=%s\n' "${dbversion}"
    printf 'active_actions_before=%s\n' "${active_actions_before}"
    printf 'active_actions_after=%s\n' "${active_actions_after}"
    printf 'enabled_media_before=%s\n' "${enabled_media_before}"
    printf 'enabled_media_after=%s\n' "${enabled_media_after}"
    printf 'enabled_connectors_before=%s\n' "${enabled_connectors_before}"
    printf 'enabled_connectors_after=%s\n' "${enabled_connectors_after}"
    printf 'zabbix_server_state=%s\n' "$(systemctl is-active zabbix-server 2>/dev/null || true)"
    printf 'zabbix_server_enabled=%s\n' "$(systemctl is-enabled zabbix-server 2>/dev/null || true)"
    printf 'restore=PASS\n'
  } >"${evidence_tmp}"
  chmod 0600 "${evidence_tmp}"
  mv "${evidence_tmp}" "${evidence_file}"
  trap - ERR
  cat "${evidence_file}" || true
}

case "${1:-}" in
  prepare)
    prepare
    ;;
  restore)
    shift
    restore_dump "$@"
    ;;
  *)
    echo "usage: $0 prepare | restore DUMP.sql.gz EXPECTED_SHA256" >&2
    exit 2
    ;;
esac
