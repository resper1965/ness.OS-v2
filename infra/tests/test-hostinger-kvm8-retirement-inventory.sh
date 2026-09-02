#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="${repo_root}/infra/scripts/inventory-hostinger-kvm8-retirement.sh"
real_path="${PATH}"
temp_dir="$(mktemp -d)"
cleanup() {
  rm -rf -- "${temp_dir}"
}
trap cleanup EXIT

bash -n "${script}"

fixture_key="${temp_dir}/fixture_host_key"
ssh-keygen -q -t ed25519 -N '' -f "${fixture_key}"
fixture_blob="$(awk '{print $2}' "${fixture_key}.pub")"
fixture_fingerprint="$(ssh-keygen -lf "${fixture_key}.pub" -E sha256 | awk '{print $2}')"
mock_bin="${temp_dir}/bin"
mkdir -p "${mock_bin}"

cat >"${mock_bin}/ssh-keyscan" <<EOF
#!/usr/bin/env bash
printf '%s %s %s\n' '148.230.77.242' 'ssh-ed25519' '${fixture_blob}'
EOF
chmod +x "${mock_bin}/ssh-keyscan"

cat >"${mock_bin}/ssh" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >"${MOCK_SSH_ARGS}"
cat >"${MOCK_REMOTE_STDIN}"
: >"${MOCK_SSH_CALLED}"
printf '%s\n' \
  'hostname=zabbix-transmutation' \
  'check_hostname=PASS' \
  'check_zabbix_quiescent=PASS' \
  'check_web_tunnel_quiescent=PASS' \
  'check_container_runtime_quiescent=PASS' \
  'provider_destruction_readiness=BLOCKED'
exit "${MOCK_SSH_EXIT:-0}"
EOF
chmod +x "${mock_bin}/ssh"

mock_called="${temp_dir}/ssh.called"
mock_args="${temp_dir}/ssh.args"
mock_stdin="${temp_dir}/remote.stdin"
export MOCK_SSH_CALLED="${mock_called}"
export MOCK_SSH_ARGS="${mock_args}"
export MOCK_REMOTE_STDIN="${mock_stdin}"

run_inventory() {
  PATH="${mock_bin}:${real_path}" bash "${script}" \
    --host-key-fingerprint "$1" \
    --verification-source provider-console
}

wrong_fingerprint='SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
if run_inventory "${wrong_fingerprint}" >"${temp_dir}/mismatch.out" 2>"${temp_dir}/mismatch.err"; then
  echo "mismatched host fingerprint was accepted" >&2
  exit 1
fi
[[ ! -e ${mock_called} ]]
grep -Fq 'no SSH connection was attempted' "${temp_dir}/mismatch.err"

if PATH="${mock_bin}:${real_path}" bash "${script}" \
    --host-key-fingerprint "${fixture_fingerprint}" \
    --verification-source known-hosts >"${temp_dir}/source.out" 2>"${temp_dir}/source.err"; then
  echo "untrusted verification source was accepted" >&2
  exit 1
fi
[[ ! -e ${mock_called} ]]
grep -Fq 'verification source must be' "${temp_dir}/source.err"

known_hosts="/home/resper/.ssh/known_hosts"
known_hosts_before="$(sha256sum "${known_hosts}" | awk '{print $1}')"
run_inventory "${fixture_fingerprint}" >"${temp_dir}/pass.out"
known_hosts_after="$(sha256sum "${known_hosts}" | awk '{print $1}')"
[[ ${known_hosts_before} == "${known_hosts_after}" ]]
[[ -e ${mock_called} ]]
grep -Fq 'host_key_verification=PASS' "${temp_dir}/pass.out"
grep -Fq 'result=INVENTORY_COMPLETE_DESTRUCTION_BLOCKED' "${temp_dir}/pass.out"
grep -Fq -- '-F /dev/null' "${mock_args}"
grep -Fq -- '-l ness_admin' "${mock_args}"
grep -Fq -- '-i /home/resper/.ssh/ness_os_hostinger_kvm8' "${mock_args}"
grep -Fq -- '-o StrictHostKeyChecking=yes' "${mock_args}"
grep -Fq -- '-o GlobalKnownHostsFile=/dev/null' "${mock_args}"
grep -Fq -- '-o HostKeyAlgorithms=ssh-ed25519' "${mock_args}"
grep -Eq -- '-o UserKnownHostsFile=/tmp/[^ ]+/known_hosts' "${mock_args}"
grep -Fq 'provider_destruction_readiness=BLOCKED' "${mock_stdin}"

if grep -Eq '(^|[;&|[:space:]])(rm|mv|install|systemctl[[:space:]]+(start|stop|restart|enable|disable|mask|unmask)|shutdown|reboot|poweroff|docker[[:space:]]+(stop|rm)|UPDATE|DELETE|DROP|INSERT|ALTER|CREATE)([;&|[:space:]]|$)' "${mock_stdin}"; then
  echo "remote inventory contains a mutating command" >&2
  exit 1
fi

rm -f -- "${mock_called}"
export MOCK_SSH_EXIT=10
if run_inventory "${fixture_fingerprint}" >"${temp_dir}/blocked.out" 2>"${temp_dir}/blocked.err"; then
  echo "remote quiescence failure returned success" >&2
  exit 1
fi
grep -Fq 'result=REMOTE_QUIESCENCE_FAILED_DESTRUCTION_BLOCKED' "${temp_dir}/blocked.out"

echo "Hostinger KVM8 retirement inventory fail-closed tests: PASS"
