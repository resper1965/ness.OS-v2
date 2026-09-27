#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="${repo_root}/infra/scripts/authentik-readiness-report.sh"
helper="${repo_root}/infra/scripts/authentik_mfa_readiness.py"
manifest="${repo_root}/config/authentik/ness-os-baseline.yaml"
runbook="${repo_root}/docs/runbooks/identity-break-glass.md"

[[ -s ${script} && -s ${helper} && -s ${manifest} && -s ${runbook} ]]
grep -q 'Read-only Authentik inventory' "${script}"
grep -q '/api/v3/core/groups/' "${script}"
grep -q '/api/v3/core/applications/' "${script}"
grep -q 'authentik_mfa_readiness.py' "${script}"
grep -q '/api/v3/authenticators/admin/' "${helper}"
grep -q '/api/v3/core/authenticated_sessions/' "${script}"
grep -q 'python3 -c' "${script}"
grep -q 'AUTHENTIK_REQUIRED_ADMIN_USERS' "${script}"
grep -q 'admin_mfa_enrolled_count=' "${helper}"
grep -q 'authentik_readiness=FAIL' "${script}"
grep -q 'AUTHENTIK_REQUIRED_ADMIN_USERS' "${helper}"
grep -q 'user.get("is_active")' "${helper}"
grep -qi 'duas pessoas distintas aprovam' "${runbook}"
grep -qi 'revogar tokens/sessões' "${runbook}"
grep -qi 'não registrar segredos' "${runbook}"
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
tr -d '\r' < "${script}" | bash -n
PYTHONPATH="${repo_root}/infra/scripts" python3 - <<'PY'
from authentik_mfa_readiness import summarize_admin_mfa

admins = ["admin-one", "admin-two"]
assert summarize_admin_mfa(admins, []) == {
    "required_count": 2,
    "enrolled_count": 0,
    "ready": False,
}
assert not summarize_admin_mfa(
    admins,
    [{"user": {"username": "admin-one", "is_active": True}}],
)["ready"]
assert not summarize_admin_mfa(
    admins,
    [{"user": {"username": "admin-one", "is_active": False}},
     {"user": {"username": "admin-two", "is_active": True}}],
)["ready"]
assert not summarize_admin_mfa(
    admins,
    [{"user": {"username": "admin-one", "is_active": True}},
     {"user": {"username": "admin-one", "is_active": True}}],
)["ready"]
assert summarize_admin_mfa(
    admins,
    [{"user": {"username": "admin-one", "is_active": True}},
     {"user": {"username": "admin-two", "is_active": True}}],
)["ready"]
assert not summarize_admin_mfa(["admin-one"], [])["ready"]
PY
echo 'authentik readiness static checks: PASS'
