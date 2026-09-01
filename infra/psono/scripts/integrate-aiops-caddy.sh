#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly caddyfile="${AIOPS_CADDYFILE:-/opt/n-infraops/app/Caddyfile}"
readonly container="${AIOPS_CADDY_CONTAINER:-ninf-caddy}"
readonly mode="${1:-stage}"

[[ -f ${caddyfile} && ! -L ${caddyfile} ]] || { echo 'AIOps Caddyfile is unavailable' >&2; exit 2; }
[[ ${mode} == stage || ${mode} == reload ]] || { echo 'usage: integrate-aiops-caddy.sh [stage|reload]' >&2; exit 3; }

if ! grep -Fqx 'cofre.ness.com.br {' "${caddyfile}"; then
  backup="${caddyfile}.pre-psono-$(date +%Y%m%dT%H%M%S%z)"
  cp -a "${caddyfile}" "${backup}"
  cat >>"${caddyfile}" <<'EOF'

# Psono Community — temporary AIOps placement; application authentication is native.
cofre.ness.com.br {
    encode zstd gzip

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "same-origin"
        -Server
    }

    reverse_proxy ness-psono:80
}
EOF
  echo "caddy_backup=${backup}"
else
  echo 'caddy_block=already_present'
fi

docker exec "${container}" caddy validate --config /etc/caddy/Caddyfile
echo 'caddy_validate=PASS'

if [[ ${mode} == reload ]]; then
  docker exec "${container}" caddy reload --config /etc/caddy/Caddyfile
  echo 'caddy_reload=PASS'
else
  echo 'caddy_reload=DEFERRED'
fi
