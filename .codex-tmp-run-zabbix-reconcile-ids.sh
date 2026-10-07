#!/usr/bin/env bash
set -euo pipefail

readonly STAGE_DIR=/run/ness-zabbix-id-reconcile
readonly EVIDENCE_DIR=/var/lib/ness-os/restore-evidence/zabbix-id-reconcile-20260902T1915-0300

cleanup() {
    sudo rm -rf "${STAGE_DIR}"
}
trap cleanup EXIT

sudo test ! -e "${EVIDENCE_DIR}"
sudo install -d -m 700 -o root -g root "${EVIDENCE_DIR}"
sudo cp /var/lib/zabbix-id-sequence-before.txt "${EVIDENCE_DIR}/before.txt"
sudo php "${STAGE_DIR}/.codex-tmp-zabbix-reconcile-ids.php" | \
    sudo tee "${EVIDENCE_DIR}/reconcile.txt"
sudo /usr/local/sbin/zabbix-id-sequence-report | \
    sudo tee "${EVIDENCE_DIR}/after.txt"
sudo awk -F '\t' '$2 == "users_groups" && $4 == $5 { found=1 } END { exit !found }' \
    "${EVIDENCE_DIR}/after.txt"
sudo find "${EVIDENCE_DIR}" -maxdepth 1 -type f -exec chmod 600 {} +
