#!/usr/bin/env bash
# Read-only progress view for the official Object Storage -> zbx-prd-01 restore.
set -Eeuo pipefail

readonly TARGET_HOST="${TARGET_HOST:-169.58.234.9}"
readonly TARGET_KEY="${TARGET_KEY:-/home/resper/.ssh/ness_os_zbx_prd_01}"
readonly TARGET_USER="${TARGET_USER:-ness_admin}"
readonly SESSION="${SESSION:-ness_zbx_object_restore}"
readonly LOG_FILE="${LOG_FILE:-/var/log/ness-os/zabbix-object-restore.log}"

ssh_cmd=(ssh -o BatchMode=yes -o ConnectTimeout=10 -o IdentitiesOnly=yes \
  -i "${TARGET_KEY}" "${TARGET_USER}@${TARGET_HOST}")

printf 'Zabbix restore progress — %s\n\n' "$(date --iso-8601=seconds)"
"${ssh_cmd[@]}" "
  if tmux has-session -t '${SESSION}' 2>/dev/null; then
    echo session=running
  else
    echo session=stopped
  fi
  echo '[latest log]'
  sudo tail -n 16 '${LOG_FILE}' 2>/dev/null || echo log=awaiting-start
  echo '[staging artifacts]'
  sudo find /var/lib/ness-os/restore-input -maxdepth 6 -type f \\
    \( -name COMPLETED -o -name SHA256SUMS -o -name '*.sql.gz' \) \\
    -printf '%TY-%Tm-%TdT%TT %s %p\\n' 2>/dev/null | tail -n 12 || true
"
