#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT="$(cd "$(dirname "$0")/../scripts" && pwd)/zabbix-proxy-set-offline-buffer.sh"
S() { bash "$SCRIPT" "$@"; }
d=$(mktemp -d); trap 'rm -rf "$d"' EXIT
export ZBX_PROXY_CONF="$d/p.conf" ZBX_SKIP_RESTART=1
printf 'Server=x\nTLSPSKFile=/k\n' >"$d/p.conf"
S >/dev/null; grep -q ProxyOfflineBuffer "$d/p.conf" && { echo "simulacao escreveu" >&2; exit 1; }
S --apply 24 >/dev/null; grep -qx 'ProxyOfflineBuffer=24' "$d/p.conf"
grep -qx 'TLSPSKFile=/k' "$d/p.conf"
S --apply 48 >/dev/null; [[ $(grep -c '^ProxyOfflineBuffer=' "$d/p.conf") == 1 ]]; grep -qx 'ProxyOfflineBuffer=48' "$d/p.conf"
ls "$d"/p.conf.bak-offlinebuffer-* >/dev/null
for bad in 0 721 abc; do S --apply "$bad" 2>/dev/null && { echo "aceitou $bad" >&2; exit 1; }; done
mkdir "$d/bin"; printf '#!/bin/sh\n[ "$1" = restart ] && [ ! -f %s/ok ] && { touch %s/ok; exit 1; }\nexit 0\n' "$d" "$d" >"$d/bin/systemctl"; chmod +x "$d/bin/systemctl"
printf 'Server=x\nProxyOfflineBuffer=1\n' >"$d/p.conf"
PATH="$d/bin:$PATH" ZBX_SKIP_RESTART="" S --apply 24 >/dev/null 2>&1 && { echo "restart falho nao falhou" >&2; exit 1; }
grep -qx 'ProxyOfflineBuffer=1' "$d/p.conf" || { echo "rollback nao restaurou" >&2; exit 1; }
echo PASS
