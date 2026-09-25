#!/usr/bin/env bash
# Public, unauthenticated F2 probes. Never follows redirects or prints headers.
set -Eeuo pipefail

command -v curl >/dev/null || { echo 'curl is required' >&2; exit 1; }

headers_file="$(mktemp /tmp/ness-authentik-precheck.XXXXXX)"
[[ ${headers_file} == /tmp/ness-authentik-precheck.* ]] || {
  echo 'unexpected temporary file' >&2
  exit 2
}
trap '[[ ${headers_file} == /tmp/ness-authentik-precheck.* ]] && rm -f -- "${headers_file}"' EXIT

failures=0

probe() {
  local name="$1" url="$2" expected_code="$3" expected_redirect_host="$4"
  shift 4
  : >"${headers_file}"

  local code location='' redirect_host='-'
  if ! code="$(curl --fail-with-body --silent --show-error \
      --output /dev/null --dump-header "${headers_file}" \
      --connect-timeout 5 --max-time 15 \
      --write-out '%{http_code}' "$@" "${url}")"; then
    printf '%s=ERROR\n' "${name}"
    failures=$((failures + 1))
    return
  fi

  location="$(awk 'BEGIN { IGNORECASE=1 } /^location:/ { sub(/^[^:]+:[[:space:]]*/, ""); sub(/\r$/, ""); value=$0 } END { print value }' "${headers_file}")"
  if [[ ${location} =~ ^https?://([^/:]+) ]]; then
    redirect_host="${BASH_REMATCH[1]}"
  elif [[ -n ${location} ]]; then
    redirect_host='relative'
  fi

  printf '%s=%s redirect_host=%s\n' "${name}" "${code}" "${redirect_host}"
  if [[ ${code} != "${expected_code}" || ${redirect_host} != "${expected_redirect_host}" ]]; then
    failures=$((failures + 1))
  fi
}

probe authentik_health \
  'https://sso.ness.com.br/-/health/live/' 200 -
probe hub_public \
  'https://hub.ness.com.br/' 200 -
probe glpi_without_session \
  'https://n-ticket.ness.com.br/' 302 sso.ness.com.br
probe n8n_without_session \
  'https://n8n.ness.com.br/' 302 sso.ness.com.br
probe zabbix_uat_sso \
  'https://zabbix-uat.ness.com.br/zabbix/index_sso.php' 302 sso.ness.com.br
probe glpi_forged_identity_headers \
  'https://n-ticket.ness.com.br/' 302 sso.ness.com.br \
  --header 'Remote-User: uat-forged' \
  --header 'X-Authentik-Username: uat-forged'

if (( failures > 0 )); then
  printf 'authentik_public_precheck=FAIL failures=%s\n' "${failures}" >&2
  exit 3
fi
echo 'authentik_public_precheck=PASS'
