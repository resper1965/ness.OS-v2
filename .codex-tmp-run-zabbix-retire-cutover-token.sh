#!/usr/bin/env bash
set -euo pipefail

readonly STAGE_DIR=/run/ness-zabbix-token-retirement
readonly EVIDENCE_DIR=/var/lib/ness-os/restore-evidence/zabbix-cutover-token-retirement-20260902T1950-0300

cleanup() {
    sudo rm -rf "${STAGE_DIR}"
}
trap cleanup EXIT

sudo test ! -e "${EVIDENCE_DIR}"
sudo install -d -m 700 -o root -g root "${EVIDENCE_DIR}"
sudo /usr/local/sbin/zabbix-api-token-state-report | \
    sudo tee "${EVIDENCE_DIR}/before.txt"
sudo php "${STAGE_DIR}/.codex-tmp-zabbix-retire-cutover-token.php" | \
    sudo tee "${EVIDENCE_DIR}/dry-run.txt"
sudo grep -q '"status":"ready","mode":"dry-run"' \
    "${EVIDENCE_DIR}/dry-run.txt"
sudo php "${STAGE_DIR}/.codex-tmp-zabbix-retire-cutover-token.php" --apply | \
    sudo tee "${EVIDENCE_DIR}/apply.txt"
sudo grep -q '"status":"retired","token_id":"4"' \
    "${EVIDENCE_DIR}/apply.txt"
sudo /usr/local/sbin/zabbix-api-token-state-report | \
    sudo tee "${EVIDENCE_DIR}/after.txt"
sudo find "${EVIDENCE_DIR}" -maxdepth 1 -type f -exec chmod 600 {} +
