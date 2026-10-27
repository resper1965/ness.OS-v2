#!/usr/bin/env bash
# Read-only as-built snapshot of one VPS, as markdown on stdout.
# Usage: NESS_AGENT_KEY=~/.ssh/nessos_agent as-built-collect.sh <host> [port]
# Never prints env vars, private IPs or container config (only names/images/state).
set -Eeuo pipefail

host="${1:?host required}"
port="${2:-22}"
key="${NESS_AGENT_KEY:?NESS_AGENT_KEY required}"

ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "${key}" -p "${port}" "ness_admin@${host}" 'sudo -n bash -s' <<'REMOTE' |
set -uo pipefail
section() { printf '\n### %s\n\n```\n' "$1"; }
end() { printf '```\n'; }

printf '## %s (%s)\n\nColetado em %s.\n' "$(hostname)" "$(. /etc/os-release; echo "${PRETTY_NAME}")" "$(TZ=America/Sao_Paulo date '+%F %H:%M %Z')"

section 'Sistema'
echo "kernel $(uname -r)"
echo "cpu $(nproc) vCPU"
free -h | awk '/^Mem|^Swap/{print $1, $2, "usado", $3}'
timedatectl show -p Timezone -p NTPSynchronized --value | paste -sd' '
end

section 'Disco'
df -hT -x tmpfs -x devtmpfs -x overlay | awk 'NR==1 || /^\/dev/'
end

section 'Serviços (ativos e habilitados)'
for u in ssh sshd ufw fail2ban docker containerd chrony systemd-timesyncd mariadb mysql postgresql nginx caddy zabbix-server zabbix-agent2 zabbix-agent; do
  systemctl cat "$u" >/dev/null 2>&1 || continue
  printf '%-18s %-9s %s\n' "$u" "$(systemctl is-active "$u")" "$(systemctl is-enabled "$u" 2>/dev/null)"
done
end

section 'Timers'
systemctl list-timers --all --no-legend --no-pager | awk '{print $(NF-1), $NF}' | grep -vE '^-' | sort -u
end

section 'Portas em escuta (fora de loopback)'
ss -Htlnp | awk '{split($4,a,":"); p=a[length(a)]; addr=substr($4,1,length($4)-length(p)-1); if (addr !~ /^(127\.|\[::1\])/) {match($0,/users:\(\("[^"]+"/); print p, addr, substr($0,RSTART+9,RLENGTH-10)}}' | sort -n -u
end

section 'UFW'
ufw status 2>/dev/null | sed -n '1p;/^--/,$p' | grep -vE '^--' | sed '/^$/d'
end

if command -v docker >/dev/null; then
  section 'Contêineres'
  docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | sort
  end
fi
REMOTE
  sed -E 's/\b(10\.[0-9]+|192\.168|172\.(1[6-9]|2[0-9]|3[01]))\.[0-9]+\.[0-9]+\b/<privado>/g'
