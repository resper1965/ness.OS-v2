#!/usr/bin/env bash
# Roda NO proxy, como root. Define ProxyOfflineBuffer (horas) mexendo só nessa linha.
# Sem --apply só mostra o que faria. Com --apply: backup, edita, reinicia e, se o serviço
# não ficar ativo, restaura o backup.
# uso: zabbix-proxy-set-offline-buffer.sh [--apply] [HORAS=24]
set -Eeuo pipefail
apply=0; [[ ${1:-} == --apply ]] && { apply=1; shift; }
hours="${1:-24}"
conf="${ZBX_PROXY_CONF:-/etc/zabbix/zabbix_proxy.conf}"
[[ $hours =~ ^[0-9]+$ ]] && ((hours >= 1 && hours <= 720)) || { echo "HORAS deve ser 1-720" >&2; exit 2; }
[[ -f $conf ]] || { echo "sem $conf" >&2; exit 2; }
# Include pode trazer valor próprio que vence o do arquivo principal
extra=$(grep -rhE '^ProxyOfflineBuffer=' /etc/zabbix/zabbix_proxy.d/ 2>/dev/null || true)
[[ -z $extra ]] || { echo "ProxyOfflineBuffer também em zabbix_proxy.d ($extra): ajuste lá" >&2; exit 3; }
echo "atual: $(grep -E '^ProxyOfflineBuffer=' "$conf" || echo '(não definido: padrão 1 h)')"
echo "novo : ProxyOfflineBuffer=$hours"
((apply)) || { echo "(simulação; use --apply)"; exit 0; }
bak="$conf.bak-offlinebuffer-$(date +%Y%m%dT%H%M%S)"
cp -p "$conf" "$bak"
if grep -qE '^ProxyOfflineBuffer=' "$conf"; then
  sed -i -E "s/^ProxyOfflineBuffer=.*/ProxyOfflineBuffer=$hours/" "$conf"
else
  printf '\nProxyOfflineBuffer=%s\n' "$hours" >>"$conf"
fi
if [[ -z ${ZBX_SKIP_RESTART:-} ]]; then
  systemctl restart zabbix-proxy
  sleep 10
  if ! systemctl is-active --quiet zabbix-proxy; then
    cp -p "$bak" "$conf"; systemctl restart zabbix-proxy || true
    echo "FALHOU: backup restaurado ($bak)" >&2; exit 1
  fi
fi
echo "OK: $(grep -E '^ProxyOfflineBuffer=' "$conf") (backup $bak)"
