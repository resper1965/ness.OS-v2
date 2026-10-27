#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="${repo_root}/infra/scripts/hub-alert-mail.sh"
tmp="$(mktemp -d)"
trap 'rm -rf -- "${tmp}"' EXIT
mkdir -p "${tmp}/bin" "${tmp}/state"
export PATH="${tmp}/bin:${PATH}" HUB_REPORT_DIR="${tmp}/state" \
  NESS_ALERT_MAIL_ENV="${tmp}/alert.env" NESS_PSONO_ENV="${tmp}/psono.env" \
  CURL_LOG="${tmp}/curl.log" CURL_STDIN="${tmp}/curl.stdin"
cat >"${tmp}/bin/curl" <<'F'
#!/usr/bin/env bash
echo "$*" >>"${CURL_LOG}"
cat >>"${CURL_STDIN}"
F
chmod +x "${tmp}/bin/curl"
echo 'RESEND_API_KEY=re_test_secret' >"${tmp}/psono.env"
echo '{"status":"degraded","glpi":{"status":"error"},"zabbix":{"status":"ok"},"detail":"x"}' >"${tmp}/state/status.json"
sends() { [[ -e "${CURL_LOG}" ]] && wc -l <"${CURL_LOG}" || echo 0; }

bash -n "${script}"

# no recipient: exits 0, no request
: >"${tmp}/alert.env"
bash "${script}"
[[ "$(sends)" == 0 ]]

# first failure sends; key only via stdin, never argv
echo 'NESS_ALERT_MAIL_TO=a@example.invalid,b@example.invalid' >"${tmp}/alert.env"
bash "${script}"
[[ "$(sends)" == 1 ]]
grep -q 're_test_secret' "${CURL_STDIN}"
! grep -q 're_test_secret' "${CURL_LOG}"

# within one hour: no second send
bash "${script}"
[[ "$(sends)" == 1 ]]

# after one hour: sends again
touch -d '2 hours ago' "${tmp}/state/alert-mail.stamp"
bash "${script}"
[[ "$(sends)" == 2 ]]

# missing status.json still sends; recovery clears the stamp
rm "${tmp}/state/status.json" "${tmp}/state/alert-mail.stamp"
bash "${script}"
[[ "$(sends)" == 3 ]]
bash "${script}" recovered
[[ "$(sends)" == 4 && ! -e "${tmp}/state/alert-mail.stamp" ]]
echo "hub-alert-mail: PASS"
