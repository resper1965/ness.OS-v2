#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="${repo_root}/infra/scripts/monitor-zabbix-proxy-reconnect.sh"
tmp="$(mktemp -d)"
trap 'rm -rf -- "${tmp}"' EXIT
mkdir -p "${tmp}/bin"
export PATH="${tmp}/bin:${PATH}" SSH_LOG="${tmp}/ssh.log"
# ssh stub: logs the remote command; answers 18/18 only if the query excludes stacavprx, else 18/19
cat >"${tmp}/bin/ssh" <<'F'
#!/usr/bin/env bash
echo "$*" >>"${SSH_LOG}"
[[ "$*" == *"p.name <> 'stacavprx'"* ]] && echo 18/18 || echo 18/19
F
chmod +x "${tmp}/bin/ssh"

bash -n "${script}"
TIMEOUT_SECONDS=5 bash "${script}" >/dev/null
grep -q "WHERE p.name <> 'stacavprx';" "${SSH_LOG}"
echo ok
