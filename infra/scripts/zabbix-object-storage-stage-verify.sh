#!/usr/bin/env bash
# Run as root on zbx-prd-01. Verifies an existing Object Storage staging set.
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }
readonly stage="${1:?usage: zabbix-object-storage-stage-verify.sh STAGING_DIR}"
readonly evidence="${stage}/VERIFICATION-$(date +%Y%m%dT%H%M%S%z).txt"

[[ -d "${stage}" && -f "${stage}/SHA256SUMS" && -f "${stage}/COMPLETED" ]] || {
  echo 'staging set is incomplete' >&2
  exit 2
}

source_file="$(awk 'NR == 1 { print $2 }' "${stage}/SHA256SUMS")"
source_root="${source_file%/*}"
dump="$(find "${stage}" -type f -name 'dbzabbix*.sql.gz' -print -quit)"
[[ -n "${dump}" ]] || { echo 'zabbix dump not found' >&2; exit 3; }

{
  echo "verified_at=$(date --iso-8601=seconds)"
  echo "stage=${stage}"
  echo 'phase=sha256'
  ( cd "${stage}" && sed "s#  ${source_root}/#  #" SHA256SUMS | sha256sum -c - )
  echo 'phase=gzip'
  gzip -t "${dump}"
  echo "dump_bytes=$(stat -c %s "${dump}")"
  echo 'staging_integrity=PASS'
} | tee "${evidence}"
