#!/usr/bin/env bash
set -Eeuo pipefail
S="$(cd "$(dirname "$0")/../scripts" && pwd)/zabbix-proxy-set-offline-buffer.sh"
d=$(mktemp -d); trap 'rm -rf "$d"' EXIT
export ZBX_PROXY_CONF="$d/p.conf" ZBX_SKIP_RESTART=1
printf 'Server=x\nTLSPSKFile=/k\n' >"$d/p.conf"
"$S" >/dev/null; grep -q ProxyOfflineBuffer "$d/p.conf" && { echo "simulacao escreveu" >&2; exit 1; }
"$S" --apply 24 >/dev/null; grep -qx 'ProxyOfflineBuffer=24' "$d/p.conf"
grep -qx 'TLSPSKFile=/k' "$d/p.conf"
"$S" --apply 48 >/dev/null; [[ $(grep -c '^ProxyOfflineBuffer=' "$d/p.conf") == 1 ]]; grep -qx 'ProxyOfflineBuffer=48' "$d/p.conf"
ls "$d"/p.conf.bak-offlinebuffer-* >/dev/null
for bad in 0 721 abc; do "$S" --apply "$bad" 2>/dev/null && { echo "aceitou $bad" >&2; exit 1; }; done
echo PASS
