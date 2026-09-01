#!/usr/bin/env bash
set -Eeuo pipefail

readonly ZABBIX_RELEASE_URL="https://repo.zabbix.com/zabbix/7.0/debian/pool/main/z/zabbix-release/zabbix-release_latest+debian12_all.deb"
readonly MARIADB_KEY_URL="https://mariadb.org/mariadb_release_signing_key.pgp"
readonly MARIADB_KEYRING="/usr/share/keyrings/mariadb-archive-keyring.gpg"
readonly MARIADB_VERSION="1:10.11.18+maria~deb12"
readonly ZABBIX_VERSION="1:7.0.27-1+debian12"

if [[ ${EUID} -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

. /etc/os-release
if [[ ${ID} != debian || ${VERSION_ID} != 12 ]]; then
  echo "this staging bootstrap requires Debian 12" >&2
  exit 1
fi

case "${1:-repositories}" in
  repositories)
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends ca-certificates curl gnupg

    temp_dir="$(mktemp -d)"
    trap 'rm -rf -- "${temp_dir}"' EXIT
    curl --fail --location --silent --show-error \
      "${ZABBIX_RELEASE_URL}" --output "${temp_dir}/zabbix-release.deb"
    dpkg --install "${temp_dir}/zabbix-release.deb"

    curl --fail --location --silent --show-error "${MARIADB_KEY_URL}" \
      --output "${temp_dir}/mariadb-release-signing-key.pgp"
    gpg --batch --yes --dearmor \
      --output "${MARIADB_KEYRING}" "${temp_dir}/mariadb-release-signing-key.pgp"
    chmod 0644 "${MARIADB_KEYRING}"
    install -m 0644 /dev/stdin /etc/apt/sources.list.d/mariadb.list <<EOF
deb [signed-by=${MARIADB_KEYRING}] https://dlm.mariadb.com/repo/mariadb-server/10.11/repo/debian bookworm main
EOF
    apt-get update
    ;;
  install)
    export DEBIAN_FRONTEND=noninteractive
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
    ;;
  *)
    echo "usage: $0 {repositories|install}" >&2
    exit 2
    ;;
esac

apt-cache policy \
  mariadb-server mariadb-client \
  zabbix-server-mysql zabbix-sql-scripts zabbix-frontend-php zabbix-apache-conf zabbix-agent2
