#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="${repo_root}/infra/scripts/zabbix-cutover-enable-production.sh"
bash -n "${script}"

tmp="$(mktemp -d)"
trap 'rm -rf -- "${tmp}"' EXIT
mkdir "${tmp}/bin"
cat >"${tmp}/bin/ufw" <<'STUB'
#!/usr/bin/env bash
echo "ufw $*" >>"${UFW_LOG}"
[[ $1 == status ]] && printf '%s' "${UFW_STATUS:-}"
exit 0
STUB
chmod +x "${tmp}/bin/ufw"
sed -n '/^# web-exposure:begin/,/^# web-exposure:end/p' "${script}" >"${tmp}/block.sh"
[[ -s ${tmp}/block.sh ]]
grep -qx 'configure_web_exposure' "${script}"
grep -qx 'assert_10051_restricted' "${script}"

no() { if "$@"; then echo "unexpected: $*" >&2; exit 1; fi; }

run() { # run env [VAR=value ...]; FN selects the function (default configure_web_exposure)
  : >"${tmp}/ufw.log"
  env -u ZBX_WEB_EXPOSURE PATH="${tmp}/bin:${PATH}" UFW_LOG="${tmp}/ufw.log" "${@}" \
    # shellcheck disable=SC2016 # expanded by the inner shell
    bash -c 'set -Eeuo pipefail; source "$1"; "${FN:-configure_web_exposure}"' _ "${tmp}/block.sh" >"${tmp}/out" 2>&1
}

# default (unset) is closed: no allow 80/443
run env
no grep -Eq 'ufw allow (80|443)' "${tmp}/ufw.log"
grep -q 'not opened' "${tmp}/out"

run env ZBX_WEB_EXPOSURE=closed
no grep -Eq 'ufw allow (80|443)' "${tmp}/ufw.log"

# public keeps legacy behavior
run env ZBX_WEB_EXPOSURE=public
grep -q 'ufw allow 80/tcp' "${tmp}/ufw.log"
grep -q 'ufw allow 443/tcp' "${tmp}/ufw.log"

# closed with a pre-existing public rule: warn, never delete
run env ZBX_WEB_EXPOSURE=closed UFW_STATUS=$'443/tcp                     ALLOW       Anywhere\n443/tcp                     ALLOW       173.245.48.0/20\n'
grep -q 'WARNING' "${tmp}/out"
no grep -Eq 'ufw (allow (80|443)|delete)' "${tmp}/ufw.log"
run env ZBX_WEB_EXPOSURE=closed UFW_STATUS=$'443/tcp                     ALLOW       173.245.48.0/20\n'
no grep -q 'WARNING' "${tmp}/out"

# broader warning coverage; Cloudflare-only rules stay silent
for line in '80,443/tcp                  ALLOW       Anywhere' 'Apache Full                 ALLOW       Anywhere' \
  'Nginx Full (v6)             ALLOW       Anywhere (v6)' '443/tcp on eth0             ALLOW       Anywhere' \
  '443/tcp (v6)                ALLOW       Anywhere (v6)'; do
  run env ZBX_WEB_EXPOSURE=closed UFW_STATUS="${line}"$'\n'
  grep -q 'WARNING' "${tmp}/out" || { echo "no warning for: ${line}" >&2; exit 1; }
done
run env ZBX_WEB_EXPOSURE=closed UFW_STATUS=$'80,443/tcp                  ALLOW       173.245.48.0/20\n443/tcp on eth0             ALLOW       2400:cb00::/32\n'
no grep -q 'WARNING' "${tmp}/out"

# 10051 open to Anywhere (v4/v6, with interface) aborts; restricted passes
for line in '10051/tcp                   ALLOW       Anywhere' '10051/tcp (v6)              ALLOW       Anywhere (v6)' \
  '10051 on eth0               ALLOW       Anywhere'; do
  if run env FN=assert_10051_restricted UFW_STATUS="${line}"$'\n'; then echo "10051 not aborted: ${line}" >&2; exit 1; fi
done
run env FN=assert_10051_restricted UFW_STATUS=$'10051/tcp                   ALLOW       203.0.113.10\n10051/tcp                   ALLOW       203.0.113.11\n'

# invalid value fails before any firewall change
if run env ZBX_WEB_EXPOSURE=open; then echo 'invalid mode accepted' >&2; exit 1; fi
no grep -q 'ufw' "${tmp}/ufw.log"
echo 'zabbix web exposure: PASS'
