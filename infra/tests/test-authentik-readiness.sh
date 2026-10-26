#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="${repo_root}/infra/scripts/authentik-readiness-report.sh"
manifest="${repo_root}/config/authentik/ness-os-baseline.yaml"

[[ -s ${script} && -s ${manifest} ]]
grep -q 'Read-only Authentik inventory' "${script}"
grep -q '/api/v3/core/groups/' "${script}"
grep -q '/api/v3/core/applications/' "${script}"
grep -q '/api/v3/authenticators/admin/' "${script}"
grep -q '/api/v3/core/authenticated_sessions/' "${script}"
grep -q 'python3 -c' "${script}"
if grep -q 'jq' "${script}"; then
  echo 'readiness report unexpectedly depends on jq' >&2
  exit 1
fi
if grep -Eq 'curl .*(-X|--request)[[:space:]]*(POST|PUT|PATCH|DELETE)' "${script}"; then
  echo 'readiness report contains a mutating HTTP request' >&2
  exit 1
fi
grep -q 'pkce: S256' "${manifest}"
grep -q 'break_glass_without_idp' "${manifest}"
bash -n "${script}"
echo 'authentik readiness static checks: PASS'
