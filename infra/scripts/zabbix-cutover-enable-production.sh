#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly server_conf=/etc/zabbix/zabbix_server.conf
readonly isolation_dropin=/etc/systemd/system/zabbix-server.service.d/10-staging-isolation.conf
readonly evidence_root=/var/lib/ness-os/restore-evidence
readonly db_name=dbzabbix

systemctl is-active --quiet mariadb
server_state="$(systemctl is-active zabbix-server 2>/dev/null || true)"
server_enabled="$(systemctl is-enabled zabbix-server 2>/dev/null || true)"
if [[ ${server_state} == inactive && ${server_enabled} == masked ]]; then
  activation_mode=initial
elif [[ ${server_state} == active && ${server_enabled} == enabled ]]; then
  activation_mode=resume
else
  printf 'unexpected zabbix-server state: active=%s enabled=%s\n' \
    "${server_state}" "${server_enabled}" >&2
  exit 2
fi
[[ -f ${server_conf} && -f ${isolation_dropin} ]]

active_actions="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${db_name}.actions WHERE status=0;")"
active_media="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${db_name}.media_type WHERE status=0;")"
active_connectors="$(mariadb --protocol=socket -NBe "SELECT COALESCE(SUM(status=0),0) FROM ${db_name}.connector;")"
[[ ${active_actions} == 0 && ${active_media} == 0 && ${active_connectors} == 0 ]]

install -d -m 0700 -o root -g root "${evidence_root}"
stamp="$(date +%Y%m%dT%H%M%S%z)"
install -o root -g root -m 0600 "${server_conf}" \
  "${evidence_root}/zabbix-server-conf-before-production-${stamp}"
install -o root -g root -m 0600 "${isolation_dropin}" \
  "${evidence_root}/zabbix-server-dropin-before-production-${stamp}"

sed -i \
  -e 's/^ListenIP=.*/ListenIP=0.0.0.0/' \
  -e '/^FpingLocation=/d' \
  -e '/^Fping6Location=/d' \
  "${server_conf}"
printf '\nFpingLocation=/usr/bin/fping\nFping6Location=/usr/bin/fping6\n' >>"${server_conf}"

# The staging network namespace allowed only the pilot and proxy addresses.
# Production polling needs outbound access to the complete monitored inventory;
# inbound TCP/10051 remains restricted by UFW to the observed proxy allowlist.
sed -i \
  -e '/^IPAddressDeny=/d' \
  -e '/^IPAddressAllow=/d' \
  -e 's/^NoNewPrivileges=true$/NoNewPrivileges=false/' \
  "${isolation_dropin}"

grep -qx 'ListenIP=0.0.0.0' "${server_conf}"
grep -qx 'FpingLocation=/usr/bin/fping' "${server_conf}"
grep -qx 'Fping6Location=/usr/bin/fping6' "${server_conf}"
grep -qx 'NoNewPrivileges=false' "${isolation_dropin}"
! grep -q '^IPAddress' "${isolation_dropin}"
getcap /usr/bin/fping | grep -q 'cap_net_raw=ep'
sudo -u zabbix /usr/bin/fping -q -c1 127.0.0.1 >/dev/null

/usr/sbin/zabbix_server -T -c "${server_conf}"
systemctl daemon-reload

ufw allow 80/tcp comment 'Zabbix production ACME and HTTPS redirect'
ufw allow 443/tcp comment 'Zabbix production HTTPS'
! ufw status | grep -Eq '^10051/tcp[[:space:]]+ALLOW[[:space:]]+Anywhere([[:space:]]|$)'

if [[ ${activation_mode} == initial ]]; then
  systemctl unmask zabbix-server
  systemctl daemon-reload
fi
systemd-analyze verify zabbix-server.service
systemctl enable --now zabbix-server

[[ "$(systemctl is-active zabbix-server)" == active ]]
ss -H -lnt 'sport = :10051' | grep -qE '(0\.0\.0\.0|\*):10051'

evidence="${evidence_root}/zabbix-production-enable-${stamp}.txt"
{
  printf 'enabled_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'listen_ip=0.0.0.0\n'
  printf 'fping_capability=pass\n'
  printf 'production_http_firewall=enabled\n'
  printf 'proxy_firewall=allowlist-only\n'
  printf 'active_actions=%s\n' "${active_actions}"
  printf 'active_media=%s\n' "${active_media}"
  printf 'active_connectors=%s\n' "${active_connectors}"
  printf 'zabbix_server_state=%s\n' "$(systemctl is-active zabbix-server)"
  printf 'zabbix_server_enabled=%s\n' "$(systemctl is-enabled zabbix-server)"
  printf 'activation_mode=%s\n' "${activation_mode}"
  printf 'production_enable=PASS\n'
} >"${evidence}"
chmod 0600 "${evidence}"
cat "${evidence}"
