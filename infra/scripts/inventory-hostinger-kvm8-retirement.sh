#!/usr/bin/env bash
# Fail-closed, read-only retirement inventory for the temporary Hostinger KVM8.
set -Eeuo pipefail

readonly TARGET_HOST="148.230.77.242"
readonly TARGET_PORT="22"
readonly TARGET_USER="ness_admin"
readonly TARGET_KEY="/home/resper/.ssh/ness_os_hostinger_kvm8"
readonly EXPECTED_HOSTNAME="zabbix-transmutation"

usage() {
  cat <<'EOF'
Usage:
  inventory-hostinger-kvm8-retirement.sh \
    --host-key-fingerprint SHA256:<43-base64-chars> \
    --verification-source provider-console|provider-support-ticket

The fingerprint must be obtained out of band for the current VM instance.
Repository documentation, known_hosts, ssh-keyscan output and an SSH warning are
not acceptable verification sources.

This command never edits known_hosts or the remote host. It performs only a
read-only inventory and always leaves provider destruction/cancellation blocked
pending separate attestations and explicit authorization.
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

expected_fingerprint=""
verification_source=""
while (($#)); do
  case "$1" in
    --host-key-fingerprint)
      (($# >= 2)) || die "missing value for --host-key-fingerprint"
      expected_fingerprint="$2"
      shift 2
      ;;
    --verification-source)
      (($# >= 2)) || die "missing value for --verification-source"
      verification_source="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

[[ ${expected_fingerprint} =~ ^SHA256:[A-Za-z0-9+/]{43}$ ]] \
  || die "a valid SHA-256 host-key fingerprint is required"
case "${verification_source}" in
  provider-console|provider-support-ticket) ;;
  *) die "verification source must be provider-console or provider-support-ticket" ;;
esac

for command_name in ssh ssh-keygen ssh-keyscan mktemp stat; do
  command -v "${command_name}" >/dev/null || die "required command not found: ${command_name}"
done

[[ -f ${TARGET_KEY} && ! -L ${TARGET_KEY} ]] \
  || die "dedicated private key is absent or is a symlink: ${TARGET_KEY}"
key_owner="$(stat -c '%u' -- "${TARGET_KEY}")"
key_mode="$(stat -c '%a' -- "${TARGET_KEY}")"
[[ ${key_owner} == "${EUID}" ]] || die "dedicated private key is not owned by the current user"
(( (8#${key_mode} & 077) == 0 )) || die "dedicated private key permits group/other access"

temp_dir="$(mktemp -d)"
cleanup() {
  rm -rf -- "${temp_dir}"
}
trap cleanup EXIT
chmod 0700 "${temp_dir}"
scan_file="${temp_dir}/scan"
candidate_file="${temp_dir}/candidate"
verified_known_hosts="${temp_dir}/known_hosts"

# A scan is discovery, not trust. Trust comes exclusively from the required
# out-of-band fingerprint, and only the matching key enters the isolated file.
if ! ssh-keyscan -4 -T 5 -p "${TARGET_PORT}" -t ed25519 "${TARGET_HOST}" \
    >"${scan_file}" 2>/dev/null; then
  die "host-key scan failed; no SSH connection was attempted"
fi

matching_key=""
while read -r scanned_host scanned_type scanned_blob _; do
  [[ ${scanned_type:-} == ssh-ed25519 && -n ${scanned_blob:-} ]] || continue
  printf '%s %s %s\n' "${scanned_host}" "${scanned_type}" "${scanned_blob}" >"${candidate_file}"
  scanned_fingerprint="$(ssh-keygen -lf "${candidate_file}" -E sha256 2>/dev/null | awk 'NR == 1 {print $2}')"
  if [[ ${scanned_fingerprint} == "${expected_fingerprint}" ]]; then
    if [[ -n ${matching_key} && ${matching_key} != "${scanned_blob}" ]]; then
      die "more than one distinct scanned key matched unexpectedly"
    fi
    matching_key="${scanned_blob}"
  fi
done <"${scan_file}"

[[ -n ${matching_key} ]] \
  || die "live ED25519 host key does not match the out-of-band fingerprint; no SSH connection was attempted"

printf '%s %s %s\n' "${TARGET_HOST}" ssh-ed25519 "${matching_key}" >"${verified_known_hosts}"
chmod 0600 "${verified_known_hosts}"

printf 'host_key_verification=PASS\n'
printf 'host_key_algorithm=ssh-ed25519\n'
printf 'host_key_fingerprint=%s\n' "${expected_fingerprint}"
printf 'verification_source=%s\n' "${verification_source}"
printf 'inventory_mode=READ_ONLY\n'

ssh_options=(
  -F /dev/null
  -4
  -p "${TARGET_PORT}"
  -l "${TARGET_USER}"
  -i "${TARGET_KEY}"
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=yes
  -o "UserKnownHostsFile=${verified_known_hosts}"
  -o GlobalKnownHostsFile=/dev/null
  -o UpdateHostKeys=no
  -o CheckHostIP=yes
  -o HostKeyAlgorithms=ssh-ed25519
  -o PasswordAuthentication=no
  -o KbdInteractiveAuthentication=no
  -o LogLevel=ERROR
)

set +e
ssh "${ssh_options[@]}" "${TARGET_HOST}" 'bash -s' -- "${EXPECTED_HOSTNAME}" <<'REMOTE_INVENTORY'
set -uo pipefail

blockers=0
expected_hostname="$1"

service_state() {
  local state
  state="$(systemctl is-active "$1" 2>/dev/null)" || true
  printf '%s\n' "${state:-unknown}"
}

service_enablement() {
  local state
  state="$(systemctl is-enabled "$1" 2>/dev/null)" || true
  printf '%s\n' "${state:-unknown}"
}

process_count() {
  local count
  if ! command -v pgrep >/dev/null; then
    printf 'unknown\n'
    return
  fi
  count="$(pgrep -xc "$1" 2>/dev/null)" || true
  printf '%s\n' "${count:-unknown}"
}

listener_count() {
  local count
  if ! command -v ss >/dev/null; then
    printf 'unknown\n'
    return
  fi
  count="$(ss -H -lnt "sport = :$1" 2>/dev/null | wc -l)" || true
  printf '%s\n' "${count:-unknown}"
}

non_loopback_listener_count() {
  local count
  if ! command -v ss >/dev/null; then
    printf 'unknown\n'
    return
  fi
  count="$(ss -H -lnt "sport = :$1" 2>/dev/null \
    | awk '$4 !~ /^127\./ && $4 !~ /^\[::1\]:/ && $4 !~ /^::1:/ {count++} END {print count + 0}')" || true
  printf '%s\n' "${count:-unknown}"
}

directory_summary() {
  label="$1"
  path="$2"
  if sudo -n test -d "${path}" 2>/dev/null; then
    bytes="$(sudo -n du -sB1 -- "${path}" 2>/dev/null | awk 'NR == 1 {print $1}')"
    files="$(sudo -n find "${path}" -xdev -type f -printf . 2>/dev/null | wc -c)"
    printf '%s_present=yes\n' "${label}"
    printf '%s_bytes=%s\n' "${label}" "${bytes:-unknown}"
    printf '%s_files=%s\n' "${label}" "${files}"
  else
    printf '%s_present=no-or-unreadable\n' "${label}"
    return 1
  fi
}

hostname_value="$(hostname 2>/dev/null || printf unknown)"
printf 'hostname=%s\n' "${hostname_value}"
printf 'kernel=%s\n' "$(uname -sr 2>/dev/null || printf unknown)"
if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  printf 'os=%s\n' "${PRETTY_NAME:-unknown}"
else
  printf 'os=unknown\n'
fi
printf 'uptime_seconds=%s\n' "$(cut -d. -f1 /proc/uptime 2>/dev/null || printf unknown)"
printf 'root_filesystem=%s\n' "$(df -B1 --output=size,used,avail,pcent / 2>/dev/null | tail -n 1 | xargs || printf unknown)"
printf 'memory_bytes=%s\n' "$(awk '/^MemTotal:/ {print $2 * 1024}' /proc/meminfo 2>/dev/null || printf unknown)"

if [[ ${hostname_value} != "${expected_hostname}" ]]; then
  printf 'check_hostname=FAIL\n'
  ((blockers++))
else
  printf 'check_hostname=PASS\n'
fi

if sudo -n true 2>/dev/null; then
  printf 'passwordless_sudo=yes\n'
else
  printf 'passwordless_sudo=no\n'
  ((blockers++))
fi

zabbix_state="$(service_state zabbix-server)"
zabbix_enablement="$(service_enablement zabbix-server)"
zabbix_processes="$(process_count zabbix_server)"
zabbix_listeners="$(listener_count 10051)"
printf 'zabbix_server_state=%s\n' "${zabbix_state}"
printf 'zabbix_server_enablement=%s\n' "${zabbix_enablement}"
printf 'zabbix_server_processes=%s\n' "${zabbix_processes}"
printf 'tcp_10051_listeners=%s\n' "${zabbix_listeners}"
if [[ ${zabbix_state} == inactive && ${zabbix_enablement} == masked \
      && ${zabbix_processes} =~ ^[0-9]+$ && ${zabbix_processes} == 0 \
      && ${zabbix_listeners} =~ ^[0-9]+$ && ${zabbix_listeners} == 0 ]]; then
  printf 'check_zabbix_quiescent=PASS\n'
else
  printf 'check_zabbix_quiescent=FAIL\n'
  ((blockers++))
fi

http_listeners="$(listener_count 80)"
https_listeners="$(listener_count 443)"
if [[ ${http_listeners} =~ ^[0-9]+$ && ${https_listeners} =~ ^[0-9]+$ ]]; then
  web_listeners="$((http_listeners + https_listeners))"
else
  web_listeners=unknown
fi
cloudflared_processes="$(process_count cloudflared)"
printf 'tcp_80_443_listeners=%s\n' "${web_listeners}"
printf 'cloudflared_processes=%s\n' "${cloudflared_processes}"
if [[ ${web_listeners} =~ ^[0-9]+$ && ${web_listeners} == 0 \
      && ${cloudflared_processes} =~ ^[0-9]+$ && ${cloudflared_processes} == 0 ]]; then
  printf 'check_web_tunnel_quiescent=PASS\n'
else
  printf 'check_web_tunnel_quiescent=FAIL\n'
  ((blockers++))
fi

docker_state="$(service_state docker)"
containerd_state="$(service_state containerd)"
dockerd_processes="$(process_count dockerd)"
printf 'docker_state=%s\n' "${docker_state}"
printf 'containerd_state=%s\n' "${containerd_state}"
printf 'dockerd_processes=%s\n' "${dockerd_processes}"
if [[ ${docker_state} != active && ${docker_state} != unknown \
      && ${containerd_state} != active && ${containerd_state} != unknown \
      && ${dockerd_processes} =~ ^[0-9]+$ && ${dockerd_processes} == 0 ]]; then
  printf 'check_container_runtime_quiescent=PASS\n'
else
  printf 'check_container_runtime_quiescent=FAIL\n'
  ((blockers++))
fi

mariadb_state="$(service_state mariadb)"
mariadb_public_listeners="$(non_loopback_listener_count 3306)"
printf 'mariadb_state=%s\n' "${mariadb_state}"
printf 'tcp_3306_non_loopback_listeners=%s\n' "${mariadb_public_listeners}"
if [[ ${mariadb_public_listeners} =~ ^[0-9]+$ && ${mariadb_public_listeners} == 0 ]]; then
  printf 'check_mariadb_not_public=PASS\n'
else
  printf 'check_mariadb_not_public=FAIL\n'
  ((blockers++))
fi
directory_summary mysql_data /var/lib/mysql || ((blockers++))
directory_summary restore_input /var/lib/ness-os/restore-input || ((blockers++))
directory_summary restore_evidence /var/lib/ness-os/restore-evidence || ((blockers++))

printf 'provider_snapshots_volumes_backups=NOT_CHECKED\n'
printf 'external_copy_checksums=ATTESTATION_REQUIRED\n'
printf 'credential_revocation=ATTESTATION_REQUIRED\n'
printf 'provider_resource_ownership=ATTESTATION_REQUIRED\n'
printf 'destruction_authorization=NOT_GRANTED_BY_THIS_SCRIPT\n'

if ((blockers == 0)); then
  printf 'remote_quiescence=PASS\n'
else
  printf 'remote_quiescence=FAIL\n'
fi
printf 'remote_quiescence_blockers=%d\n' "${blockers}"
printf 'provider_destruction_readiness=BLOCKED\n'

((blockers == 0)) || exit 10
REMOTE_INVENTORY
ssh_status=$?
set -e

case "${ssh_status}" in
  0)
    printf 'inventory_transport=PASS\n'
    printf 'result=INVENTORY_COMPLETE_DESTRUCTION_BLOCKED\n'
    ;;
  10)
    printf 'inventory_transport=PASS\n'
    printf 'result=REMOTE_QUIESCENCE_FAILED_DESTRUCTION_BLOCKED\n'
    exit 10
    ;;
  *)
    printf 'inventory_transport=FAIL\n' >&2
    printf 'result=INVENTORY_INCOMPLETE_DESTRUCTION_BLOCKED\n' >&2
    exit "${ssh_status}"
    ;;
esac
