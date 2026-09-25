#!/usr/bin/env bash
# Read-only Authentik inventory. Never prints tokens, object payloads or emails.
set -Eeuo pipefail

readonly base_url="${AUTHENTIK_URL:?AUTHENTIK_URL is required}"
readonly token="${AUTHENTIK_TOKEN:?AUTHENTIK_TOKEN is required}"
command -v curl >/dev/null || { echo 'curl is required' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'python3 is required' >&2; exit 1; }

api_get() {
  local path="$1"
  curl --fail --silent --show-error \
    --connect-timeout 5 --max-time 15 \
    -H "Authorization: Bearer ${token}" \
    -H 'Accept: application/json' \
    "${base_url%/}${path}"
}

api_count() {
  api_get "$1" | python3 -c \
    'import json, sys; print(json.load(sys.stdin).get("pagination", {}).get("count", 0))'
}

printf 'authentik_readiness_at=%s\n' "$(date --iso-8601=seconds)"
curl --fail --silent --show-error --max-time 10 "${base_url%/}/-/health/live/" >/dev/null
echo 'core_health=PASS'

for group in platform_admin ness-os-platform-admin admin noc soc helpdesk gestao usuarios; do
  count="$(api_count "/api/v3/core/groups/?name=${group}&page_size=1")"
  printf 'group_%s=%s\n' "${group//-/_}" "${count}"
done

for slug in hub zabbix glpi n8n; do
  count="$(api_count "/api/v3/core/applications/?slug=${slug}&page_size=1")"
  printf 'application_%s=%s\n' "${slug}" "${count}"
done

provider_count="$(api_count '/api/v3/providers/all/?page_size=1')"
printf 'provider_count=%s\n' "${provider_count}"

for type in totp webauthn static duo email sms endpoint; do
  count="$(api_count "/api/v3/authenticators/admin/${type}/?page_size=1")"
  printf 'authenticator_%s_count=%s\n' "${type}" "${count}"
done

session_count="$(api_count '/api/v3/core/authenticated_sessions/?page_size=1')"
printf 'authenticated_session_count=%s\n' "${session_count}"
echo 'authentik_readiness=PASS'
