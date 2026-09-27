#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
runner="${repo_root}/infra/scripts/hub-session-readiness.sh"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "${tmpdir}"' EXIT
fake_bin="${tmpdir}/bin"
curl_log="${tmpdir}/curl.log"
mkdir -p "${fake_bin}"

printf '%s\n' '#!/usr/bin/env bash' 'printf "called\\n" >>"${HUB_TEST_CURL_LOG}"' 'exit 99' \
  >"${fake_bin}/curl"
chmod +x "${fake_bin}/curl"

bash -n "${runner}"

static_output="$(env -u HUB_SESSION_EXECUTE \
  PATH="${fake_bin}:${PATH}" HUB_TEST_CURL_LOG="${curl_log}" \
  bash "${runner}" 2>&1)"
grep -q '^browser_token_exposure=0$' <<<"${static_output}"
grep -q '^cookie_controls=PASS$' <<<"${static_output}"
grep -q '^edge_controls=PASS$' <<<"${static_output}"
grep -q '^network_requests=0$' <<<"${static_output}"
grep -q '^Hub session readiness: PASS (static)$' <<<"${static_output}"
grep -q 'copied_bearer_revocation=PASS' "${runner}"
grep -q 'copied bearer token remained valid after logout' "${runner}"
grep -q 'env.HUB_UAT_PASSWORD' "${runner}"
grep -q 'unset HUB_UAT_EMAIL HUB_UAT_PASSWORD' "${runner}"
! grep -q -- '--arg password' "${runner}" || {
  echo 'Hub UAT password is exposed in jq process arguments' >&2
  exit 1
}
[[ ! -e "${curl_log}" ]]

if guard_output="$(env -u HUB_SESSION_EXECUTE \
  PATH="${fake_bin}:${PATH}" HUB_TEST_CURL_LOG="${curl_log}" \
  HUB_UAT_EMAIL='uat@example.invalid' HUB_UAT_PASSWORD='not-a-real-secret' \
  bash "${runner}" --execute-contained 2>&1)"; then
  printf 'runner unexpectedly executed without HUB_SESSION_EXECUTE=1\n' >&2
  exit 1
fi
grep -q 'contained probe requires HUB_SESSION_EXECUTE=1' <<<"${guard_output}"
if grep -q 'not-a-real-secret' <<<"${guard_output}"; then
  echo 'guard output exposed the supplied test secret' >&2
  exit 1
fi
[[ ! -e "${curl_log}" ]]

printf 'Hub session readiness runner checks: PASS\n'
