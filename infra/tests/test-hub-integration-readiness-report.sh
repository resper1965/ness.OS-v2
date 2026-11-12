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

secret="do-not-print-glpi-token"
output="$(NINF_GLPI_USER_TOKEN="$secret" env -u NINF_LOKI_URL PATH="$TEMP_DIR:$PATH" bash "$REPORT")"
[[ "$output" == *"glpi_user_token_configured=yes"* ]]
[[ "$output" == *"loki_url_configured=no"* ]]
[[ "$output" != *"$secret"* ]]

echo "Hub integration readiness secret report: PASS"
