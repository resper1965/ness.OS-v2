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
    "llm_key": "NINF_LLM_API_KEY",
    "loki_url": "NINF_LOKI_URL",
}
for label, variable in checks.items():
    print(f"{label}_configured={'yes' if os.getenv(variable, '').strip() else 'no'}")
PY
