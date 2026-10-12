#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
production="${repo_root}/app/docker-compose.yml"
development="${repo_root}/app/docker-compose.dev.yml"
workflow="${repo_root}/.github/workflows/ci-backend.yml"

fail() {
  printf 'release compose contract: FAIL: %s\n' "$1" >&2
  exit 1
}

service_block() {
  local file="$1"
  local service="$2"
  awk -v service="${service}" '
    { sub(/\r$/, "") }
    $0 == "  " service ":" { found=1; print; next }
    found && /^  [A-Za-z0-9_.-]+:$/ { exit }
    found { print }
  ' "${file}"
}

require_line() {
  local text="$1"
  local expected="$2"
  grep -Fqx -- "${expected}" <<<"${text}" || fail "missing ${expected}"
}

require_absent() {
  local text="$1"
  local pattern="$2"
  if grep -Fq -- "${pattern}" <<<"${text}"; then
    fail "unexpected ${pattern}"
  fi
}

for service in api worker-alerts worker-ml; do
  block="$(service_block "${production}" "${service}")"
  require_line "${block}" '    image: ${NINF_API_IMAGE:?NINF_API_IMAGE is required}'
  require_absent "${block}" '    build:'
  require_absent "${block}" './backend/app:/app/app:ro'
done

frontend="$(service_block "${production}" frontend)"
require_line "${frontend}" '    image: ${NINF_FRONTEND_IMAGE:?NINF_FRONTEND_IMAGE is required}'
require_absent "${frontend}" '    build:'

for service in api worker-alerts worker-ml; do
  block="$(service_block "${development}" "${service}")"
  require_line "${block}" '    image: ness-api:dev'
  require_line "${block}" '    build:'
  require_line "${block}" '      - ./backend/app:/app/app:ro'
done

frontend="$(service_block "${development}" frontend)"
require_line "${frontend}" '    image: ness-frontend:dev'
require_line "${frontend}" '    build:'

require_line "$(tr -d '\r' <"${workflow}")" '        bash infra/tests/test-release-compose-contract.sh'
grep -Fq -- 'NINF_API_IMAGE=registry.example/ness/api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "${workflow}" || fail 'CI lacks immutable API placeholder'
grep -Fq -- 'NINF_FRONTEND_IMAGE=registry.example/ness/frontend@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' "${workflow}" || fail 'CI lacks immutable frontend placeholder'
grep -Fq -- '-f app/docker-compose.dev.yml' "${workflow}" || fail 'CI does not validate development Compose'

printf 'release compose contract: PASS\n'
