#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="${repo_root}/infra/scripts/authentik-public-precheck.sh"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "${tmpdir}"' EXIT
fake_bin="${tmpdir}/bin"
mkdir -p "${fake_bin}"

cat >"${fake_bin}/curl" <<'CURL'
#!/usr/bin/env bash
set -Eeuo pipefail
url=''
headers_file=''
forged=0
while (($#)); do
  case "$1" in
    --dump-header)
      headers_file="$2"
      shift 2
      ;;
    --header)
      [[ "$2" == 'Remote-User: uat-forged' || "$2" == 'X-Authentik-Username: uat-forged' ]] && forged=1
      shift 2
      ;;
    http://*|https://*)
      url="$1"
      shift
      ;;
    *)
      shift
      ;;
  esac
done

case "${url}" in
  https://sso.ness.com.br/*|-)
    code=200
    ;;
  https://hub.ness.com.br/*)
    code=200
    ;;
  https://n-ticket.ness.com.br/*|https://n8n.ness.com.br/*|https://zabbix-uat.ness.com.br/*)
    code=302
    ;;
  *)
    exit 2
    ;;
esac

if (( forged )) && [[ "${AUTHENTIK_TEST_FAIL_FORGED:-0}" == 1 ]]; then
  code=200
fi
if [[ "${code}" == 302 ]]; then
  printf 'HTTP/1.1 302 Found\r\nLocation: https://sso.ness.com.br/application/\r\n\r\n' >"${headers_file}"
else
  printf 'HTTP/1.1 %s OK\r\n\r\n' "${code}" >"${headers_file}"
fi
printf '%s' "${code}"
CURL
chmod +x "${fake_bin}/curl"

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
output="$(PATH="${fake_bin}:${PATH}" bash "${script}")"
grep -q '^glpi_forged_identity_headers=302 redirect_host=sso.ness.com.br$' <<<"${output}"
grep -q '^authentik_public_precheck=PASS$' <<<"${output}"
if failure_output="$(AUTHENTIK_TEST_FAIL_FORGED=1 PATH="${fake_bin}:${PATH}" bash "${script}" 2>&1)"; then
  echo 'public precheck accepted a forged identity header' >&2
  exit 1
fi
grep -q '^glpi_forged_identity_headers=200 redirect_host=-$' <<<"${failure_output}"
grep -q '^authentik_public_precheck=FAIL failures=1$' <<<"${failure_output}"
echo 'authentik public precheck contract checks: PASS'
