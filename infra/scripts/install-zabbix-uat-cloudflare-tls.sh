#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly cert_source=/tmp/zabbix-uat-origin.pem
readonly key_source=/tmp/zabbix-uat-origin.key
readonly cidr_source=/tmp/cloudflare-ips-v4.txt
readonly cert_dir=/etc/ssl/ness-os

[[ -s "${cert_source}" && -s "${key_source}" && -s "${cidr_source}" ]]
openssl x509 -noout -modulus -in "${cert_source}" | openssl sha256 >/tmp/cert-modulus
openssl rsa -noout -modulus -in "${key_source}" | openssl sha256 >/tmp/key-modulus
cmp -s /tmp/cert-modulus /tmp/key-modulus

install -d -m 0700 -o root -g root "${cert_dir}"
install -m 0644 -o root -g root "${cert_source}" "${cert_dir}/zabbix-uat-origin.pem"
install -m 0600 -o root -g root "${key_source}" "${cert_dir}/zabbix-uat-origin.key"
grep -qxF 'Listen 443' /etc/apache2/ports.conf || printf '%s\n' 'Listen 443' >>/etc/apache2/ports.conf
install -m 0644 -o root -g root /tmp/ness-zabbix-uat-cloudflare-ssl.conf /etc/apache2/sites-available/ness-zabbix-uat-cloudflare-ssl.conf
a2enmod ssl headers >/dev/null
a2ensite ness-zabbix-uat-cloudflare-ssl >/dev/null
apache2ctl configtest

while IFS= read -r cidr; do
  [[ "${cidr}" =~ ^[0-9./]+$ ]] || continue
  ufw allow from "${cidr}" to any port 443 proto tcp comment 'Cloudflare to Zabbix UAT'
done <"${cidr_source}"
ufw --force enable
systemctl restart apache2
rm -f "${cert_source}" "${key_source}" "${cidr_source}" /tmp/cert-modulus /tmp/key-modulus
systemctl is-active apache2
systemctl is-active zabbix-server || true
systemctl is-enabled zabbix-server || true
