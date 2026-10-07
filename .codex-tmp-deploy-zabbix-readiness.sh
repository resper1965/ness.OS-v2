#!/usr/bin/env bash
set -euo pipefail

readonly APP_DIR=/opt/n-infraops/app
readonly STAGE_DIR=/run/ness-zabbix-readiness
readonly EVIDENCE_DIR=/opt/n-infraops/rollback/zabbix-hub-readiness-20260902T185348-0300

rollback() {
    local exit_code=$?
    if [[ "${exit_code}" -eq 0 ]]; then
        return
    fi
    if [[ -f "${EVIDENCE_DIR}/zabbix.py" ]]; then
        sudo cp -a "${EVIDENCE_DIR}/zabbix.py" \
            "${APP_DIR}/backend/app/integrations/zabbix.py"
    fi
    if [[ -f "${EVIDENCE_DIR}/zabbix_readiness.py" ]]; then
        sudo cp -a "${EVIDENCE_DIR}/zabbix_readiness.py" \
            "${APP_DIR}/backend/app/integrations/zabbix_readiness.py"
    else
        sudo rm -f "${APP_DIR}/backend/app/integrations/zabbix_readiness.py"
    fi
    exit "${exit_code}"
}

cleanup() {
    sudo rm -rf "${STAGE_DIR}"
}
trap rollback ERR
trap cleanup EXIT

sudo test ! -e "${EVIDENCE_DIR}"
sudo install -d -m 700 -o root -g root "${EVIDENCE_DIR}"
sudo cp -a "${APP_DIR}/backend/app/integrations/zabbix.py" \
    "${EVIDENCE_DIR}/zabbix.py"
if sudo test -f "${APP_DIR}/backend/app/integrations/zabbix_readiness.py"; then
    sudo cp -a "${APP_DIR}/backend/app/integrations/zabbix_readiness.py" \
        "${EVIDENCE_DIR}/zabbix_readiness.py"
fi

sudo install -m 644 -o root -g root "${STAGE_DIR}/zabbix.py" \
    "${APP_DIR}/backend/app/integrations/zabbix.py"
sudo install -m 644 -o root -g root "${STAGE_DIR}/zabbix_readiness.py" \
    "${APP_DIR}/backend/app/integrations/zabbix_readiness.py"
sudo docker exec ninf-api python -c \
    'path="/app/app/integrations/zabbix.py"; compile(open(path, encoding="utf-8").read(), path, "exec")'
sudo docker exec ninf-api python -m app.integrations.zabbix_readiness | \
    sudo tee "${EVIDENCE_DIR}/result.txt"
sudo grep -Eq '^status=ready mode=read-only transport=json-rpc version=[0-9A-Za-z._-]+ authenticated=True visible_hosts=[0-9]+ writes=0$' \
    "${EVIDENCE_DIR}/result.txt"
sudo chmod 600 "${EVIDENCE_DIR}/result.txt"
