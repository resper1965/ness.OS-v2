#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly db_name=dbzabbix
readonly env_file=/etc/ness-os/zabbix-cutover-bootstrap.env
readonly api_url=https://zabbix.ness.com.br/api_jsonrpc.php
readonly evidence_root=/var/lib/ness-os/restore-evidence

[[ -r ${env_file} ]]
systemctl is-active --quiet zabbix-server apache2 mariadb
[[ "$(systemctl --failed --no-legend | wc -l)" == 0 ]]

proxy_total="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${db_name}.proxy;")"
proxy_fresh="$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${db_name}.proxy p JOIN ${db_name}.proxy_rtdata r USING(proxyid) WHERE r.lastaccess>=UNIX_TIMESTAMP()-300 AND r.compatibility=1;")"
[[ ${proxy_total} == 18 && ${proxy_fresh} == 18 ]]

[[ "$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${db_name}.actions WHERE status=0;")" == 0 ]]
[[ "$(mariadb --protocol=socket -NBe "SELECT COUNT(*) FROM ${db_name}.media_type WHERE status=0;")" == 0 ]]
[[ "$(mariadb --protocol=socket -NBe "SELECT COALESCE(SUM(status=0),0) FROM ${db_name}.connector;")" == 0 ]]

token="$(sed -n 's/^ZABBIX_API_TOKEN=//p' "${env_file}" | tail -1)"
[[ ${#token} -ge 32 ]]

api_call() {
  local request=${1:?request is required}
  local response
  response="$(curl --fail --silent --show-error \
    --resolve zabbix.ness.com.br:443:127.0.0.1 \
    --header 'Content-Type: application/json-rpc' \
    --header "Authorization: Bearer ${token}" \
    --data-binary "${request}" \
    "${api_url}")"
  if jq -e '.error' >/dev/null <<<"${response}"; then
    jq '.error' <<<"${response}" >&2
    return 1
  fi
  printf '%s\n' "${response}"
}

for actionid in 2 3 4 5 6; do
  request="$(jq -nc --arg id "${actionid}" '{jsonrpc:"2.0",method:"action.update",params:{actionid:$id,status:"0"},id:1}')"
  api_call "${request}" | jq -e --arg id "${actionid}" '.result.actionids == [$id]' >/dev/null
done

request="$(jq -nc '{jsonrpc:"2.0",method:"mediatype.update",params:{mediatypeid:"1",status:"0"},id:2}')"
api_call "${request}" | jq -e '.result.mediatypeids == ["1"]' >/dev/null

active_action_ids="$(mariadb --protocol=socket --batch --raw --skip-column-names "${db_name}" \
  -e "SELECT GROUP_CONCAT(actionid ORDER BY actionid SEPARATOR ',') FROM actions WHERE status=0;")"
active_media_ids="$(mariadb --protocol=socket --batch --raw --skip-column-names "${db_name}" \
  -e "SELECT GROUP_CONCAT(mediatypeid ORDER BY mediatypeid SEPARATOR ',') FROM media_type WHERE status=0;")"
[[ ${active_action_ids} == '2,3,4,5,6' ]]
[[ ${active_media_ids} == '1' ]]

install -d -m 0700 -o root -g root "${evidence_root}"
evidence="${evidence_root}/zabbix-production-alerting-$(date +%Y%m%dT%H%M%S%z).txt"
{
  printf 'enabled_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'proxy_total=%s\n' "${proxy_total}"
  printf 'proxy_fresh_5m=%s\n' "${proxy_fresh}"
  printf 'active_action_ids=%s\n' "${active_action_ids}"
  printf 'active_media_ids=%s\n' "${active_media_ids}"
  printf 'enabled_connectors=0\n'
  printf 'alerting_enable=PASS\n'
} >"${evidence}"
chmod 0600 "${evidence}"
cat "${evidence}"

unset token
