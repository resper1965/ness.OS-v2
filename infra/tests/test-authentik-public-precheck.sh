#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="${repo_root}/infra/scripts/authentik-public-precheck.sh"

[[ -s ${script} ]]
grep -q 'Never follows redirects or prints headers' "${script}"
grep -q 'zabbix-uat.ness.com.br/zabbix/index_sso.php' "${script}"
grep -q 'Remote-User: uat-forged' "${script}"
grep -q 'X-Authentik-Username: uat-forged' "${script}"
grep -q 'authentik_public_precheck=PASS' "${script}"
if grep -Eq '(-L|--location|Authorization:|Set-Cookie)' "${script}"; then
  echo 'public precheck can follow redirects or expose authentication material' >&2
  exit 1
fi
bash -n "${script}"
echo 'authentik public precheck static checks: PASS'
