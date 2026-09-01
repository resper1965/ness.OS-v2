#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="${repo_root}/infra/scripts/verify-zabbix-kvm8-post-restore.sh"

bash -n "${script}"

for required in \
  'EUID' \
  'systemctl is-active mariadb' \
  "sport = :3306" \
  'systemctl is-active zabbix-server' \
  'systemctl is-enabled zabbix-server' \
  'pgrep -x zabbix_server' \
  "sport = :10051" \
  'systemctl is-active apache2' \
  'systemctl is-active zabbix-agent2' \
  'IPAddressDeny=any' \
  'IPAddressAllow=localhost' \
  'NTPSynchronized' \
  'restore-[0-9]*.txt' \
  'restore=PASS' \
  "== 0:600" \
  'database-direct-after-fail-closed' \
  'dbversion' \
  '7000000' \
  'active_actions_present' \
  'enabled_media_present' \
  'enabled_connectors_present' \
  'post_restore_verification=%s'; do
  grep -Fq "${required}" "${script}"
done

if grep -Eq 'systemctl[[:space:]]+(start|restart|enable|unmask)|(^|[[:space:]])(UPDATE|DELETE|DROP|INSERT|ALTER|CREATE)[[:space:]]' "${script}"; then
  echo "verifier contains a mutating service or database command" >&2
  exit 1
fi

if grep -Eqi '(password|secret)[[:space:]]*=' "${script}"; then
  echo "verifier appears to record a credential" >&2
  exit 1
fi

echo "zabbix KVM8 post-restore verifier static checks: PASS"
