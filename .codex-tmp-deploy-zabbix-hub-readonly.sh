#!/usr/bin/env bash
set -euo pipefail

readonly APP_DIR=/opt/n-infraops/app
readonly STAGE_DIR=/run/ness-zabbix-hub-deploy
readonly EVIDENCE_DIR=/opt/n-infraops/rollback/zabbix-hub-readonly-20260902T1942-0300-retry1
readonly INTEGRATION_ENV=/etc/ness-os/zabbix-integration.env
readonly TOKEN_FILE=/run/ness-zabbix-hub-readonly/token

had_env=0
had_readiness=0
deployment_started=0

rollback() {
    local status=$?
    if [[ ${status} -ne 0 && ${deployment_started} -eq 1 ]]; then
        sudo cp "${EVIDENCE_DIR}/docker-compose.yml" "${APP_DIR}/docker-compose.yml"
        sudo cp "${EVIDENCE_DIR}/zabbix.py" \
            "${APP_DIR}/backend/app/integrations/zabbix.py"
        if [[ ${had_readiness} -eq 1 ]]; then
            sudo cp "${EVIDENCE_DIR}/zabbix_readiness.py" \
                "${APP_DIR}/backend/app/integrations/zabbix_readiness.py"
        else
            sudo rm -f "${APP_DIR}/backend/app/integrations/zabbix_readiness.py"
        fi
        if [[ ${had_env} -eq 1 ]]; then
            sudo cp "${EVIDENCE_DIR}/zabbix-integration.env" "${INTEGRATION_ENV}"
        else
            sudo rm -f "${INTEGRATION_ENV}"
        fi
        (cd "${APP_DIR}" && sudo docker compose up -d --no-deps --force-recreate api) \
            2>&1 | sudo tee "${EVIDENCE_DIR}/rollback-recreate.txt" >/dev/null || true
        echo rolled_back | sudo tee "${EVIDENCE_DIR}/result.txt" >/dev/null
    fi
    sudo rm -rf "${STAGE_DIR}"
    exit "${status}"
}
trap rollback EXIT

sudo test ! -e "${EVIDENCE_DIR}"
sudo install -d -m 700 -o root -g root "${EVIDENCE_DIR}"
sudo cp "${APP_DIR}/docker-compose.yml" "${EVIDENCE_DIR}/docker-compose.yml"
sudo cp "${APP_DIR}/backend/app/integrations/zabbix.py" \
    "${EVIDENCE_DIR}/zabbix.py"
if sudo test -f "${APP_DIR}/backend/app/integrations/zabbix_readiness.py"; then
    had_readiness=1
    sudo cp "${APP_DIR}/backend/app/integrations/zabbix_readiness.py" \
        "${EVIDENCE_DIR}/zabbix_readiness.py"
fi
if sudo test -f "${INTEGRATION_ENV}"; then
    had_env=1
    sudo cp "${INTEGRATION_ENV}" "${EVIDENCE_DIR}/zabbix-integration.env"
fi
sudo test "$(sudo wc -c "${TOKEN_FILE}" | awk '{print $1}')" -eq 64
sudo grep -Eq '^[[:xdigit:]]{64}$' "${TOKEN_FILE}"

deployment_started=1
sudo bash -c 'umask 077
{
    printf "%s\n" "NINF_ZABBIX_URL=https://zabbix.ness.com.br/api_jsonrpc.php"
    printf "%s" "NINF_ZABBIX_API_TOKEN="
    cat /run/ness-zabbix-hub-readonly/token
    printf "\n"
} > /etc/ness-os/zabbix-integration.env.new
mv /etc/ness-os/zabbix-integration.env.new /etc/ness-os/zabbix-integration.env'

sudo awk '
    { print }
    $0 == "      - /etc/ness-os/glpi-integration.env" {
        print "      - /etc/ness-os/zabbix-integration.env"
    }
' "${APP_DIR}/docker-compose.yml" | sudo tee "${APP_DIR}/docker-compose.yml.new" >/dev/null
sudo grep -q '^      - /etc/ness-os/zabbix-integration.env$' \
    "${APP_DIR}/docker-compose.yml.new"
sudo mv "${APP_DIR}/docker-compose.yml.new" "${APP_DIR}/docker-compose.yml"
sudo install -m 644 "${STAGE_DIR}/zabbix.py" \
    "${APP_DIR}/backend/app/integrations/zabbix.py"
sudo install -m 644 "${STAGE_DIR}/zabbix_readiness.py" \
    "${APP_DIR}/backend/app/integrations/zabbix_readiness.py"
sudo install -m 700 "${STAGE_DIR}/hub-integration-readiness-report.sh" \
    /usr/local/sbin/hub-integration-readiness-report

cd "${APP_DIR}"
sudo docker compose config --quiet
sudo docker compose up -d --no-deps --force-recreate api 2>&1 | \
    sudo tee "${EVIDENCE_DIR}/api-recreate.txt" >/dev/null
sudo docker compose exec -T api python -m app.integrations.zabbix_readiness | \
    sudo tee "${EVIDENCE_DIR}/zabbix-readiness.txt"
sudo grep -q 'status=ready mode=read-only transport=json-rpc' \
    "${EVIDENCE_DIR}/zabbix-readiness.txt"
sudo docker compose exec -T api python -m app.integrations.glpi_readiness | \
    sudo tee "${EVIDENCE_DIR}/glpi-readiness.txt"
sudo grep -q 'status=ready mode=dry-run transport=private' \
    "${EVIDENCE_DIR}/glpi-readiness.txt"
sudo /usr/local/sbin/hub-integration-readiness-report | \
    sudo tee "${EVIDENCE_DIR}/integration-presence.txt"
sudo grep -q '^zabbix_token_configured=yes$' \
    "${EVIDENCE_DIR}/integration-presence.txt"
curl --fail --silent --show-error --max-time 20 \
    -o /dev/null -w '%{http_code}\n' https://hub.ness.com.br/ | \
    sudo tee "${EVIDENCE_DIR}/hub-http-status.txt"
sudo grep -q '^200$' "${EVIDENCE_DIR}/hub-http-status.txt"
echo deployed | sudo tee "${EVIDENCE_DIR}/result.txt" >/dev/null
sudo find "${EVIDENCE_DIR}" -maxdepth 1 -type f -exec chmod 600 {} +
