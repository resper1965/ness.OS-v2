#!/usr/bin/env bash
set -euo pipefail

readonly STAGE_DIR=/run/ness-zabbix-hub-provision
readonly EVIDENCE_DIR=/var/lib/ness-os/restore-evidence/zabbix-hub-readonly-20260902T1920-0300-retry2

cleanup() {
    sudo rm -rf "${STAGE_DIR}"
}
trap cleanup EXIT

sudo test ! -e "${EVIDENCE_DIR}"
sudo install -d -m 700 -o root -g root "${EVIDENCE_DIR}"
sudo php "${STAGE_DIR}/.codex-tmp-zabbix-hub-readonly.php" | \
    sudo tee "${EVIDENCE_DIR}/dry-run.txt"
sudo grep -q '"status":"ready","mode":"dry-run"' \
    "${EVIDENCE_DIR}/dry-run.txt"
sudo php "${STAGE_DIR}/.codex-tmp-zabbix-hub-readonly.php" --apply | \
    sudo tee "${EVIDENCE_DIR}/apply.txt"
sudo python3 "${STAGE_DIR}/.codex-tmp-zabbix-token-probe.py" | \
    sudo tee "${EVIDENCE_DIR}/probe.txt"
sudo grep -q '"disallowed_method_denied":true,"write_operations":0' \
    "${EVIDENCE_DIR}/probe.txt"
sudo find "${EVIDENCE_DIR}" -maxdepth 1 -type f -exec chmod 600 {} +
