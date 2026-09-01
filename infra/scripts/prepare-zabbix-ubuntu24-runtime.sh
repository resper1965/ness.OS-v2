#!/usr/bin/env bash
set -Eeuo pipefail

readonly MARIADB_VERSION="1:10.11.19+maria~ubu2404"
readonly ZABBIX_VERSION="1:7.0.27-1+ubuntu24.04"

[[ ${EUID} -eq 0 ]] || { echo "run as root" >&2; exit 1; }
. /etc/os-release
[[ ${ID} == ubuntu && ${VERSION_ID} == 24.04 ]] || {
  echo "this runtime bootstrap requires Ubuntu 24.04" >&2
  exit 1
}

[[ ${1:-} == install ]] || {
  echo "usage: $0 install" >&2
  exit 2
}

policy_backup=""
if [[ -e /usr/sbin/policy-rc.d ]]; then
  policy_backup="$(mktemp)"
  cp --preserve=all /usr/sbin/policy-rc.d "${policy_backup}"
fi

restore_policy() {
  if [[ -n ${policy_backup} ]]; then
    cp --preserve=all "${policy_backup}" /usr/sbin/policy-rc.d
    rm -f -- "${policy_backup}"
  else
    rm -f /usr/sbin/policy-rc.d
  fi
}
trap restore_policy EXIT

install -m 0755 /dev/stdin /usr/sbin/policy-rc.d <<'EOF'
#!/bin/sh
exit 101
EOF

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends \
  "mariadb-server=${MARIADB_VERSION}" \
  "mariadb-client=${MARIADB_VERSION}" \
  "zabbix-server-mysql=${ZABBIX_VERSION}" \
  "zabbix-sql-scripts=${ZABBIX_VERSION}" \
  "zabbix-frontend-php=${ZABBIX_VERSION}" \
  "zabbix-apache-conf=${ZABBIX_VERSION}" \
  "zabbix-agent2=${ZABBIX_VERSION}"

restore_policy
trap - EXIT

systemctl disable --now zabbix-server zabbix-agent2 apache2 >/dev/null 2>&1 || true
systemctl mask zabbix-server
systemctl enable --now mariadb
apt-mark hold \
  zabbix-server-mysql zabbix-sql-scripts zabbix-frontend-php \
  zabbix-apache-conf zabbix-agent2

printf 'runtime-bootstrap=PASS\n'
