#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mode=static
base_url="${HUB_BASE_URL:-https://hub.ness.com.br}"

usage() {
  printf '%s\n' \
    'Usage: infra/scripts/hub-session-readiness.sh [--execute-contained]' \
    '' \
    'Default: validate repository session controls without network access.' \
    'Live UAT requires --execute-contained, HUB_SESSION_EXECUTE=1,' \
    'HUB_UAT_EMAIL and HUB_UAT_PASSWORD.'
}

fail() {
  printf 'Hub session readiness: FAIL: %s\n' "$1" >&2
  exit 1
}

while (($#)); do
  case "$1" in
    --execute-contained)
      mode=execute
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

auth_source="${repo_root}/app/frontend/src/hooks/useAuth.tsx"
app_source="${repo_root}/app/frontend/src/App.tsx"
push_source="${repo_root}/app/frontend/src/components/PushNotificationToggle.tsx"
session_source="${repo_root}/app/backend/app/core/session.py"
compose_file="${repo_root}/app/docker-compose.yml"
caddy_file="${repo_root}/app/Caddyfile"

for source in \
  "${auth_source}" "${app_source}" "${push_source}" "${session_source}" \
  "${compose_file}" "${caddy_file}"; do
  [[ -r "${source}" ]] || fail "required source is not readable: ${source}"
done

! grep -qE 'ninf_token|localStorage.*TOKEN|stream\?token=' \
  "${auth_source}" "${app_source}" "${push_source}" || \
  fail 'frontend still exposes the browser session token'
grep -q 'httponly=True' "${session_source}" || fail 'HttpOnly cookie is not enforced'
grep -q 'samesite="strict"' "${session_source}" || fail 'SameSite Strict is not enforced'
grep -q 'session_cookie_secure' "${session_source}" || fail 'Secure cookie setting is absent'
grep -q 'NINF_SESSION_COOKIE_SECURE.*true' "${compose_file}" || \
  fail 'Compose does not default the production cookie to Secure'
! grep -q 'VITE_API_URL=http://localhost' "${compose_file}" || \
  fail 'frontend image contains a runtime localhost API override'
grep -q 'Strict-Transport-Security' "${caddy_file}" || fail 'Hub HSTS header is absent'
grep -q 'header @auth Cache-Control "no-store"' "${caddy_file}" || \
  fail 'authentication responses are not marked no-store at the edge'

printf 'browser_token_exposure=0\n'
printf 'cookie_controls=PASS\n'
printf 'edge_controls=PASS\n'

if [[ "${mode}" == static ]]; then
  printf 'network_requests=0\n'
  printf 'Hub session readiness: PASS (static)\n'
  exit 0
fi

[[ "${HUB_SESSION_EXECUTE:-}" == 1 ]] || \
  fail 'contained probe requires HUB_SESSION_EXECUTE=1'
[[ -n "${HUB_UAT_EMAIL:-}" ]] || fail 'HUB_UAT_EMAIL is required'
[[ -n "${HUB_UAT_PASSWORD:-}" ]] || fail 'HUB_UAT_PASSWORD is required'
command -v curl >/dev/null 2>&1 || fail 'curl is required'
command -v jq >/dev/null 2>&1 || fail 'jq is required'

base_url="${base_url%/}"
[[ "${base_url}" =~ ^https://[^/]+$ ]] || fail 'HUB_BASE_URL must be an HTTPS origin'
origin="${base_url}"
tmpdir="$(mktemp -d)"
chmod 700 "${tmpdir}"
trap 'rm -rf -- "${tmpdir}"' EXIT

jq -n \
  --arg email "${HUB_UAT_EMAIL}" \
  --arg password "${HUB_UAT_PASSWORD}" \
  '{email: $email, password: $password}' >"${tmpdir}/login.json"
chmod 600 "${tmpdir}/login.json"

login_status="$(curl --silent --show-error --connect-timeout 5 --max-time 20 \
  --request POST \
  --header "Origin: ${origin}" \
  --header 'Content-Type: application/json' \
  --data-binary "@${tmpdir}/login.json" \
  --cookie-jar "${tmpdir}/cookies" \
  --dump-header "${tmpdir}/login.headers" \
  --output "${tmpdir}/login.body" \
  --write-out '%{http_code}' \
  "${base_url}/api/auth/login")" || fail 'login request failed'
[[ "${login_status}" == 200 ]] || fail 'login did not return HTTP 200'
jq -e 'has("id") and has("email") and has("role") and (has("access_token") | not)' \
  "${tmpdir}/login.body" >/dev/null || fail 'browser login response shape is unsafe'

cookie_header="${tmpdir}/session-cookie.header"
grep -i '^set-cookie: ninf_session=' "${tmpdir}/login.headers" >"${cookie_header}" || \
  fail 'session cookie was not issued'
grep -qi 'httponly' "${cookie_header}" || fail 'live cookie is missing HttpOnly'
grep -qi 'secure' "${cookie_header}" || fail 'live cookie is missing Secure'
grep -qi 'samesite=strict' "${cookie_header}" || fail 'live cookie is missing SameSite Strict'
! grep -qi 'domain=' "${cookie_header}" || fail 'live cookie is not host-only'

me_status="$(curl --silent --show-error --connect-timeout 5 --max-time 20 \
  --cookie "${tmpdir}/cookies" \
  --output /dev/null --write-out '%{http_code}' \
  "${base_url}/api/auth/me")" || fail 'authenticated session request failed'
[[ "${me_status}" == 200 ]] || fail 'session cookie did not authenticate /api/auth/me'

sse_exit=0
curl --silent --show-error --connect-timeout 5 --max-time 3 \
  --cookie "${tmpdir}/cookies" \
  --dump-header "${tmpdir}/sse.headers" \
  --output /dev/null \
  "${base_url}/api/incidents/stream" 2>/dev/null || sse_exit=$?
[[ "${sse_exit}" == 0 || "${sse_exit}" == 28 ]] || fail 'SSE request failed'
grep -qE '^HTTP/[^ ]+ 200' "${tmpdir}/sse.headers" || \
  fail 'cookie-authenticated SSE did not return HTTP 200'

logout_status="$(curl --silent --show-error --connect-timeout 5 --max-time 20 \
  --request POST \
  --header "Origin: ${origin}" \
  --cookie "${tmpdir}/cookies" \
  --cookie-jar "${tmpdir}/cookies" \
  --output /dev/null --write-out '%{http_code}' \
  "${base_url}/api/auth/logout")" || fail 'logout request failed'
[[ "${logout_status}" == 204 ]] || fail 'logout did not return HTTP 204'

after_logout_status="$(curl --silent --show-error --connect-timeout 5 --max-time 20 \
  --cookie "${tmpdir}/cookies" \
  --output /dev/null --write-out '%{http_code}' \
  "${base_url}/api/auth/me")" || fail 'post-logout request failed'
[[ "${after_logout_status}" == 401 ]] || fail 'session remained valid after logout'

printf 'login_cookie=PASS\n'
printf 'session_me=PASS\n'
printf 'sse_cookie_auth=PASS token_in_url=0\n'
printf 'logout_invalidation=PASS\n'
printf 'Hub session readiness: PASS (contained live)\n'
