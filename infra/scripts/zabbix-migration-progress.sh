#!/usr/bin/env bash
# Read-only progress view for the direct Zabbix migration transfer.
set -Eeuo pipefail

readonly SOURCE_HOST="144.91.72.202"
readonly SOURCE_PORT="2222"
readonly SOURCE_KEY="${SOURCE_KEY:-/home/resper/.ssh/id_ed25519_stackvps}"
readonly TARGET_HOST="148.230.77.242"
readonly TARGET_KEY="${TARGET_KEY:-/home/resper/.ssh/ness_os_hostinger_kvm8}"
readonly STAMP="20260826T220019-0300"
readonly LOG_FILE="/var/tmp/ness-zabbix-direct-transfer-20260828.log"
readonly TARGET_ROOT="/var/lib/ness-os/restore-input"

source_ssh=(ssh -p "${SOURCE_PORT}" -o BatchMode=yes -o ConnectTimeout=10 \
  -o IdentitiesOnly=yes -i "${SOURCE_KEY}" "ness_admin@${SOURCE_HOST}")
target_ssh=(ssh -o BatchMode=yes -o ConnectTimeout=10 -o IdentitiesOnly=yes \
  -i "${TARGET_KEY}" "ness_admin@${TARGET_HOST}")

printf 'Zabbix migration progress — %s\n\n' "$(date --iso-8601=seconds)"

printf '[automation session]\n'
if tmux has-session -t ness_zbx_direct_agent 2>/dev/null; then
  echo state=running
else
  echo state=stopped
fi

printf '\n[source transfer log]\n'
"${source_ssh[@]}" '
  if test -f /var/tmp/ness-zabbix-direct-transfer-20260828.log; then
    tail -n 12 /var/tmp/ness-zabbix-direct-transfer-20260828.log
  else
    echo log=absent
  fi
'

printf '\n[target artifact]\n'
"${target_ssh[@]}" "
  final='${TARGET_ROOT}/dbzabbix-${STAMP}.sql.gz'
  partial=\"\${final}.partial\"
  if test -f \"\${final}\"; then
    stat -c 'final_bytes=%s final_mtime=%y' \"\${final}\"
  elif test -f \"\${partial}\"; then
    stat -c 'partial_bytes=%s partial_mtime=%y' \"\${partial}\"
  else
    echo artifact=absent
  fi
"

printf '\nInterpretation: transfer=PASS plus final_bytes means the copy passed; '
printf 'state=stopped or stage=failed without transfer=PASS requires investigation.\n'
