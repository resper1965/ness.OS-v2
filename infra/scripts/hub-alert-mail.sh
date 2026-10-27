#!/usr/bin/env bash
# Sends the monitor alert (or, with "recovered", the recovery notice) via the Resend API.
# Single place to add other channels (e.g. mobile push) later.
set -euo pipefail
dir=${HUB_REPORT_DIR:-/var/lib/ness-os/hub-integration}
conf=${NESS_ALERT_MAIL_ENV:-/etc/ness-os/alert-mail.env}
psono=${NESS_PSONO_ENV:-/etc/ness-os/psono.env}
stamp=$dir/alert-mail.stamp
mode=${1:-failed}
umask 077

# Reads KEY from an env file without sourcing it; strips optional quotes.
val() { [[ -r $1 ]] && sed -n "s/^$2=//p" "$1" | tail -n1 | tr -d "\"'" || true; }

to=$(val "$conf" NESS_ALERT_MAIL_TO)
if [[ -z $to ]]; then
  echo "hub-alert-mail: NESS_ALERT_MAIL_TO not set; skipping"
  exit 0
fi
if [[ $mode == recovered ]]; then
  rm -f -- "$stamp"
elif [[ -e $stamp ]] && (( $(date +%s) - $(stat -c %Y "$stamp") < 3600 )); then
  exit 0
fi
key=$(val "$conf" RESEND_API_KEY)
# ponytail: reusa a chave do Psono; upgrade path: chave Resend própria do monitor
[[ -n $key ]] || key=$(val "$psono" RESEND_API_KEY)
if [[ -z $key ]]; then
  echo "hub-alert-mail: no RESEND_API_KEY; skipping"
  exit 0
fi

work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
MAIL_TO=$to MAIL_MODE=$mode STATUS_FILE=$dir/status.json python3 - >"$work/payload.json" <<'PY'
import json, os
mode = os.environ["MAIL_MODE"]
try:
    with open(os.environ["STATUS_FILE"]) as f:
        s = json.load(f)
    lines = [f"{k}: {s[k].get('status', '?') if isinstance(s.get(k), dict) else '?'}"
             for k in ("zabbix", "glpi", "workers", "delivery")]
    lines += [f"status: {s.get('status', '?')}", f"detail: {s.get('detail', '-')}",
              f"checked_at: {s.get('checked_at', '-')}"]
except (OSError, ValueError, AttributeError):
    lines = ["status.json ausente ou ilegível"]
subject = "[ness.OS] Monitor do hub recuperado" if mode == "recovered" else "[ness.OS] Monitor do hub com falha"
print(json.dumps({
    "from": "ness.OS Monitor <monitor@ness.com.br>",
    "to": [a.strip() for a in os.environ["MAIL_TO"].split(",") if a.strip()],
    "subject": subject,
    "text": "\n".join(lines) + "\n",
}))
PY
if printf 'header = "Authorization: Bearer %s"\n' "$key" | curl -fsS -o /dev/null --max-time 15 --config - \
  -H 'Content-Type: application/json' --data-binary @"$work/payload.json" https://api.resend.com/emails; then
  [[ $mode == recovered ]] || touch -- "$stamp"
else
  echo "hub-alert-mail: send failed" >&2
  exit 1
fi
