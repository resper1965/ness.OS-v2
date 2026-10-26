#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "${tmpdir}"' EXIT

mock_bin="${tmpdir}/bin"
network_log="${tmpdir}/network.log"
mkdir -p "${mock_bin}"

for command_name in ssh ssh-keyscan scp rsync; do
  cat >"${mock_bin}/${command_name}" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$0 $*" >>"${NETWORK_LOG}"
exit 99
EOF
  chmod +x "${mock_bin}/${command_name}"
done

scripts=(
  infra/scripts/inventory-hostinger-kvm8-retirement.sh
  infra/scripts/transfer-zabbix-backup-to-kvm8.sh
  infra/scripts/transfer-zabbix-kvm8-to-prd.sh
  infra/scripts/zabbix-migration-progress.sh
)

for relative_script in "${scripts[@]}"; do
  script="${repo_root}/${relative_script}"
  bash -n "${script}"
  set +e
  output="$(PATH="${mock_bin}:${PATH}" NETWORK_LOG="${network_log}" bash "${script}" 2>&1)"
  status=$?
  set -e
  [[ ${status} -eq 64 ]]
  grep -Fq 'retired and outside the authorized asset scope' <<<"${output}"
done

[[ ! -e ${network_log} ]]
echo "Hostinger KVM8 retired-asset network guards: PASS"
