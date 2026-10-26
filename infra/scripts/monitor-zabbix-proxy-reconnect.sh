#!/usr/bin/env bash
set -Eeuo pipefail

readonly target_host="${TARGET_HOST:-169.58.234.9}"
readonly target_user="${TARGET_USER:-ness_admin}"
readonly target_key="${TARGET_KEY:-/home/resper/.ssh/ness_os_zbx_prd_01}"
readonly timeout_seconds="${TIMEOUT_SECONDS:-900}"
readonly started="$(date +%s)"

target_ssh=(ssh -i "${target_key}" -o IdentitiesOnly=yes -o BatchMode=yes \
  -o StrictHostKeyChecking=yes -o ConnectTimeout=7 "${target_user}@${target_host}")

while (( $(date +%s) - started < timeout_seconds )); do
  now="$(date --iso-8601=seconds)"
  fresh="$("${target_ssh[@]}" \
    "sudo mariadb --protocol=socket --batch --skip-column-names dbzabbix -e \"SELECT CONCAT(COALESCE(SUM(r.lastaccess>UNIX_TIMESTAMP()-300),0),'/',COUNT(*)) FROM proxy p LEFT JOIN proxy_rtdata r ON r.proxyid=p.proxyid;\"")"
  printf '%s proxies_fresh_5m=%s\n' "${now}" "${fresh}"
  [[ ${fresh} == 18/18 ]] && exit 0
  sleep 30
done

echo 'proxy reconnect timeout' >&2
exit 1
