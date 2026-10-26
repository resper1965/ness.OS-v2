#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

readonly token_file="${CLOUDFLARE_TOKEN_FILE:-/home/resper/.secrets/cloudflare-dns-token}"
readonly api_root=https://api.cloudflare.com/client/v4
readonly zone_name=ness.com.br
readonly record_name=zabbix.ness.com.br
readonly source_ip=144.91.72.202
readonly target_ip=169.58.234.9

operation="${1:-check}"
[[ ${operation} == check || ${operation} == cutover || ${operation} == rollback ]] || {
  echo 'usage: cloudflare-zabbix-dns-cutover.sh check | cutover | rollback' >&2
  exit 2
}

[[ -f ${token_file} ]] || { echo 'token file is missing' >&2; exit 4; }
[[ "$(stat -c %a "${token_file}")" == 600 ]] || { echo 'token file mode must be 600' >&2; exit 4; }
token="$(tr -d '\r\n' <"${token_file}")"
(( ${#token} >= 40 && ${#token} <= 80 )) || { echo 'token length must be between 40 and 80 characters' >&2; exit 4; }
[[ ${token} =~ ^[A-Za-z0-9_-]+$ ]] || { echo 'token contains unexpected characters' >&2; exit 4; }
command -v curl >/dev/null || { echo 'curl is unavailable' >&2; exit 4; }
command -v python3 >/dev/null || { echo 'python3 is unavailable' >&2; exit 4; }

api() {
  local method=$1 path=$2 body=${3:-}
  if [[ -n ${body} ]]; then
    curl --fail-with-body --silent --show-error \
      --request "${method}" \
      --header "Authorization: Bearer ${token}" \
      --header 'Content-Type: application/json' \
      --data "${body}" \
      "${api_root}${path}"
  else
    curl --fail-with-body --silent --show-error \
      --request "${method}" \
      --header "Authorization: Bearer ${token}" \
      --header 'Content-Type: application/json' \
      "${api_root}${path}"
  fi
}

zones="$(api GET "/zones?name=${zone_name}&status=active")"
if ! zone_id="$(python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("success") is True and len(d.get("result", [])) == 1; print(d["result"][0]["id"])' <<<"${zones}")"; then
  echo 'Cloudflare zone lookup failed' >&2
  exit 5
fi

records="$(api GET "/zones/${zone_id}/dns_records?type=A&name=${record_name}")"
if ! record_fields="$(python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("success") is True and len(d.get("result", [])) == 1; r=d["result"][0]; print("\t".join((r["id"],r["type"],r["name"],r["content"],str(r["ttl"]),str(r["proxied"]).lower())))' <<<"${records}")"; then
  echo 'Cloudflare DNS record lookup failed' >&2
  exit 5
fi
IFS=$'\t' read -r record_id record_type returned_name before_content before_ttl before_proxied <<<"${record_fields}"
[[ ${record_type} == A && ${returned_name} == "${record_name}" ]]
[[ ${before_proxied} == false ]]

if [[ ${operation} == check ]]; then
  printf 'zone=%s\nrecord=%s\ncontent=%s\nttl=%s\nproxied=%s\ntoken_access=PASS\n' \
    "${zone_name}" "${record_name}" "${before_content}" "${before_ttl}" "${before_proxied}"
  unset token
  exit 0
fi

if [[ ${operation} == cutover ]]; then
  expected=${source_ip}
  desired=${target_ip}
else
  expected=${target_ip}
  desired=${source_ip}
fi

if [[ ${before_content} == "${desired}" ]]; then
  change_state=already_applied
elif [[ ${before_content} == "${expected}" ]]; then
  payload="{\"content\":\"${desired}\"}"
  changed="$(api PATCH "/zones/${zone_id}/dns_records/${record_id}" "${payload}")"
  changed_content="$(python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("success") is True; print(d["result"]["content"])' <<<"${changed}")"
  [[ ${changed_content} == "${desired}" ]]
  change_state=applied
else
  printf 'unexpected current address for %s: %s\n' "${record_name}" "${before_content}" >&2
  exit 3
fi

after="$(api GET "/zones/${zone_id}/dns_records/${record_id}")"
after_fields="$(python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("success") is True; r=d["result"]; print("\t".join((r["type"],r["content"],str(r["ttl"]),str(r["proxied"]).lower())))' <<<"${after}")"
IFS=$'\t' read -r after_type after_content after_ttl after_proxied <<<"${after_fields}"
[[ ${after_type} == A ]]
[[ ${after_content} == "${desired}" ]]
[[ ${after_ttl} == "${before_ttl}" ]]
[[ ${after_proxied} == "${before_proxied}" ]]
unset token

printf 'operation=%s\nchange_state=%s\nbefore=%s\nafter=%s\nttl=%s\nproxied=%s\ndns_change=PASS\n' \
  "${operation}" "${change_state}" "${before_content}" "${after_content}" "${after_ttl}" "${after_proxied}"
