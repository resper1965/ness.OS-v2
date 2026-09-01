#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

if ! dpkg-query -W -f='${Status}' locales 2>/dev/null | grep -qx 'install ok installed'; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y locales
fi

sed -i -E 's|^[#[:space:]]*(pt_BR.UTF-8 UTF-8)$|\1|' /etc/locale.gen
grep -qxF 'pt_BR.UTF-8 UTF-8' /etc/locale.gen || printf '%s\n' 'pt_BR.UTF-8 UTF-8' >>/etc/locale.gen
locale-gen pt_BR.UTF-8
locale -a | grep -Eiq '^pt_BR\.utf-?8$'
systemctl restart apache2
systemctl is-active apache2
systemctl is-active zabbix-server || true
systemctl is-enabled zabbix-server || true
