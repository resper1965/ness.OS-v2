#!/usr/bin/env bash
set -euo pipefail

readonly APP_DIR=/opt/n-infraops/app
readonly STAGE_DIR=/run/ness-glpi-ticket-idempotency
readonly EVIDENCE_DIR=/opt/n-infraops/rollback/glpi-ticket-idempotency-20260902T2025-0300-retry3
deployment_started=0

rollback() {
    local status=$?
    if [[ ${status} -ne 0 && ${deployment_started} -eq 1 ]]; then
        sudo cp "${EVIDENCE_DIR}/docker-compose.yml" "${APP_DIR}/docker-compose.yml"
        sudo cp "${EVIDENCE_DIR}/glpi.py" \
            "${APP_DIR}/backend/app/integrations/glpi.py"
        sudo cp "${EVIDENCE_DIR}/alerts.py" \
            "${APP_DIR}/backend/app/workers/alerts.py"
        (cd "${APP_DIR}" && sudo docker compose up -d --no-deps \
            --force-recreate api worker-alerts) 2>&1 | \
            sudo tee "${EVIDENCE_DIR}/rollback-recreate.txt" >/dev/null || true
        echo rolled_back | sudo tee "${EVIDENCE_DIR}/result.txt" >/dev/null
    fi
    sudo rm -rf "${STAGE_DIR}"
    exit "${status}"
}
trap rollback EXIT

sudo test ! -e "${EVIDENCE_DIR}"
sudo install -d -m 700 -o root -g root "${EVIDENCE_DIR}"
sudo cp "${APP_DIR}/docker-compose.yml" "${EVIDENCE_DIR}/docker-compose.yml"
sudo cp "${APP_DIR}/backend/app/integrations/glpi.py" "${EVIDENCE_DIR}/glpi.py"
sudo cp "${APP_DIR}/backend/app/workers/alerts.py" "${EVIDENCE_DIR}/alerts.py"

deployment_started=1
sudo awk '
    $0 ~ /^  worker-alerts:\r?$/ { in_worker = 1 }
    in_worker && $0 ~ /^    env_file: \.env\r?$/ {
        print "    env_file:"
        print "      - .env"
        print "      - /etc/ness-os/glpi-integration.env"
        print "      - /etc/ness-os/zabbix-integration.env"
        changed++
        in_worker = 0
        next
    }
    { print }
    END { if (changed != 1) exit 42 }
' "${APP_DIR}/docker-compose.yml" | sudo tee "${APP_DIR}/docker-compose.yml.new" >/dev/null
sudo test "$(sudo grep -c '/etc/ness-os/glpi-integration.env' \
    "${APP_DIR}/docker-compose.yml.new")" -eq 2
sudo test "$(sudo grep -c '/etc/ness-os/zabbix-integration.env' \
    "${APP_DIR}/docker-compose.yml.new")" -eq 2
sudo mv "${APP_DIR}/docker-compose.yml.new" "${APP_DIR}/docker-compose.yml"
sudo install -m 644 "${STAGE_DIR}/glpi.py" \
    "${APP_DIR}/backend/app/integrations/glpi.py"
sudo install -m 644 "${STAGE_DIR}/alerts.py" \
    "${APP_DIR}/backend/app/workers/alerts.py"

cd "${APP_DIR}"
sudo docker compose config --quiet
sudo docker compose up -d --no-deps --force-recreate api worker-alerts 2>&1 | \
    sudo tee "${EVIDENCE_DIR}/recreate.txt" >/dev/null
sudo docker compose exec -T api python -m app.integrations.glpi_readiness | \
    sudo tee "${EVIDENCE_DIR}/glpi-readiness.txt"
sudo docker compose exec -T api python -m app.integrations.zabbix_readiness | \
    sudo tee "${EVIDENCE_DIR}/zabbix-readiness.txt"
sudo docker compose exec -T worker-alerts python - <<'PY' | \
    sudo tee "${EVIDENCE_DIR}/worker-readiness.txt"
import os
from app.integrations.glpi import GLPIClient
from app.workers.alerts import ensure_glpi_ticket

assert GLPIClient
assert ensure_glpi_ticket
assert os.environ.get("NINF_GLPI_APP_TOKEN", "").strip()
assert os.environ.get("NINF_GLPI_USER_TOKEN", "").strip()
assert os.environ.get("NINF_ZABBIX_API_TOKEN", "").strip()
print("status=ready imports=yes glpi_credentials=yes zabbix_token=yes writes=0")
PY
sudo grep -q 'status=ready mode=dry-run transport=private' \
    "${EVIDENCE_DIR}/glpi-readiness.txt"
sudo grep -q 'status=ready mode=read-only transport=json-rpc' \
    "${EVIDENCE_DIR}/zabbix-readiness.txt"
sudo grep -q 'status=ready imports=yes glpi_credentials=yes zabbix_token=yes writes=0' \
    "${EVIDENCE_DIR}/worker-readiness.txt"
echo deployed | sudo tee "${EVIDENCE_DIR}/result.txt" >/dev/null
sudo find "${EVIDENCE_DIR}" -maxdepth 1 -type f -exec chmod 600 {} +
