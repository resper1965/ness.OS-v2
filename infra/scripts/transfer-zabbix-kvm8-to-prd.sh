#!/usr/bin/env bash
set -Eeuo pipefail

retired_asset_guard() {
  echo "ERROR: Hostinger KVM8 retired and outside the authorized asset scope" >&2
  exit 64
}
retired_asset_guard

readonly SOURCE_HOST="${SOURCE_HOST:-148.230.77.242}"
readonly SOURCE_USER="${SOURCE_USER:-ness_admin}"
readonly SOURCE_KEY="${SOURCE_KEY:-/home/resper/.ssh/ness_os_hostinger_kvm8}"
readonly TARGET_HOST="${TARGET_HOST:-169.58.234.9}"
readonly TARGET_USER="${TARGET_USER:-ness_admin}"
readonly TARGET_KEY="${TARGET_KEY:-/home/resper/.ssh/ness_os_zbx_prd_01}"
readonly TARGET_ROOT="/var/lib/ness-os/restore-input"

source_file="${1:-}"
expected_sha="${2:-}"

[[ ${source_file} == /var/lib/ness-os/restore-input/dbzabbix-*.sql.gz ]] || {
  echo "unexpected source backup path" >&2
  exit 2
}
[[ ${expected_sha} =~ ^[0-9a-f]{64}$ ]] || {
  echo "expected SHA-256 is invalid" >&2
  exit 2
}
[[ -f ${SOURCE_KEY} && -f ${TARGET_KEY} ]]

source_ssh=(ssh -i "${SOURCE_KEY}" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes "${SOURCE_USER}@${SOURCE_HOST}")
target_ssh=(ssh -i "${TARGET_KEY}" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes "${TARGET_USER}@${TARGET_HOST}")

source_sha="$("${source_ssh[@]}" "sudo sha256sum -- '${source_file}'" | awk '{print $1}')"
[[ ${source_sha} == "${expected_sha}" ]]
"${source_ssh[@]}" "sudo gzip -t -- '${source_file}'"

backup_stamp="$(basename "${source_file}" .sql.gz | sed 's/^dbzabbix-//')"
target_file="${TARGET_ROOT}/dbzabbix-${backup_stamp}.sql.gz"
target_partial="${target_file}.partial"

"${target_ssh[@]}" "sudo install -d -m 0700 '${TARGET_ROOT}'; sudo rm -f -- '${target_partial}'"
set +e
"${source_ssh[@]}" "sudo cat -- '${source_file}'" \
  | "${target_ssh[@]}" "sudo sh -c 'umask 077; cat > \"${target_partial}\"'"
status=("${PIPESTATUS[@]}")
set -e
if [[ ${status[0]} -ne 0 || ${status[1]} -ne 0 ]]; then
  "${target_ssh[@]}" "sudo rm -f -- '${target_partial}'"
  echo "transfer failed" >&2
  exit 3
fi

target_sha="$("${target_ssh[@]}" "sudo sha256sum -- '${target_partial}'" | awk '{print $1}')"
if [[ ${target_sha} != "${expected_sha}" ]]; then
  "${target_ssh[@]}" "sudo rm -f -- '${target_partial}'"
  echo "target checksum mismatch" >&2
  exit 4
fi
"${target_ssh[@]}" "sudo mv -- '${target_partial}' '${target_file}'; sudo chmod 0600 '${target_file}'"

printf 'source_sha256=%s\n' "${source_sha}"
printf 'target_sha256=%s\n' "${target_sha}"
printf 'target_file=%s\n' "${target_file}"
printf 'transfer=PASS\n'
