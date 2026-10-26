#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
REPORT="$SCRIPT_DIR/../scripts/hub-integration-readiness-report.sh"
TEMP_DIR="$(mktemp -d /tmp/hub-readiness.XXXXXX)"
trap 'rm -rf "$TEMP_DIR"' EXIT

cat >"$TEMP_DIR/docker" <<'DOCKER'
#!/usr/bin/env bash
exec python3 -
DOCKER
chmod +x "$TEMP_DIR/docker"

run_report() {
  local key="$1"
  if [[ "$2" == "missing" ]]; then
    env -u NINF_N8N_WEBHOOK_API_KEY PATH="$TEMP_DIR:$PATH" bash "$REPORT"
  else
    NINF_N8N_WEBHOOK_API_KEY="$key" PATH="$TEMP_DIR:$PATH" bash "$REPORT"
  fi
}

valid_key="01234567890123456789012345678901"
output="$(run_report "$valid_key" configured)"
[[ "$output" == *"n8n_webhook_auth_configured=yes"* ]]
[[ "$output" == *"n8n_webhook_auth_strength=ok"* ]]
[[ "$output" != *"$valid_key"* ]]

output="$(run_report "short" configured)"
[[ "$output" == *"n8n_webhook_auth_configured=yes"* ]]
[[ "$output" == *"n8n_webhook_auth_strength=weak"* ]]

output="$(run_report "" missing)"
[[ "$output" == *"n8n_webhook_auth_configured=no"* ]]
[[ "$output" == *"n8n_webhook_auth_strength=missing"* ]]

echo "Hub integration readiness secret report: PASS"
