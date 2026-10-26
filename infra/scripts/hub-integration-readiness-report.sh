#!/usr/bin/env bash
set -euo pipefail

# Read-only presence report. Values are never printed.
docker exec -i ninf-api python - <<'PY'
import os

checks = {
    "zabbix_url": "NINF_ZABBIX_URL",
    "zabbix_token": "NINF_ZABBIX_API_TOKEN",
    "glpi_url": "NINF_GLPI_URL",
    "glpi_app_token": "NINF_GLPI_APP_TOKEN",
    "glpi_user_token": "NINF_GLPI_USER_TOKEN",
    "gemini_key": "NINF_GEMINI_API_KEY",
    "whatsapp_recipient": "NINF_WHATSAPP_NOC_GROUP_ID",
    "loki_url": "NINF_LOKI_URL",
}
n8n_webhook_key = os.getenv("NINF_N8N_WEBHOOK_API_KEY", "").strip()
for label, variable in checks.items():
    print(f"{label}_configured={'yes' if os.getenv(variable, '').strip() else 'no'}")
print(f"n8n_webhook_auth_configured={'yes' if n8n_webhook_key else 'no'}")
print(
    "n8n_webhook_auth_strength="
    + ("ok" if len(n8n_webhook_key) >= 32 else "weak" if n8n_webhook_key else "missing")
)
PY
