#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly gate_epoch="$(date -d '2026-08-30T17:59:56-03:00' +%s)"
readonly samples=/var/lib/ness-os/restore-evidence/zabbix-pilot-cavan-samples.tsv
readonly evidence_root=/var/lib/ness-os/restore-evidence
readonly db_name=dbzabbix

(( $(date +%s) >= gate_epoch )) || { echo 'pilot gate has not completed 24 hours' >&2; exit 2; }
[[ -f ${samples} ]]
systemctl is-active --quiet zabbix-server mariadb
[[ "$(systemctl --failed --no-legend | wc -l)" == 0 ]]

systemctl start ness-zabbix-pilot-sample.service

stats="$(awk -F '\t' '
  NR==1 { next }
  NF!=11 { malformed++; next }
  {
    valid++
    if (first=="") first=$1
    last=$1
    if ($2!="active") server_bad++
    if ($4!=2 || $5!=2) host_bad++
    if ($6!=0 || $7!=0 || $8!=0) channel_bad++
    if ($10!=0) fping_bad++
    if ($11 !~ /10873:[0-9]+,10874:[0-9]+/) freshness_bad++
    if ($9<unsupported_min || unsupported_min=="") unsupported_min=$9
    if ($9>unsupported_max || unsupported_max=="") unsupported_max=$9
    if ($3!=0) failed_unit_samples++
  }
  END {
    printf "valid_samples=%d\nmalformed_samples=%d\nfirst_valid=%s\nlast_valid=%s\nserver_bad=%d\nhost_bad=%d\nchannel_bad=%d\nfping_bad=%d\nfreshness_bad=%d\nunsupported_min=%d\nunsupported_max=%d\nfailed_unit_samples=%d\n", valid,malformed,first,last,server_bad,host_bad,channel_bad,fping_bad,freshness_bad,unsupported_min,unsupported_max,failed_unit_samples
  }
' "${samples}")"

value() { awk -F= -v key="$1" '$1==key {print $2; exit}' <<<"${stats}"; }

(( $(value valid_samples) >= 275 ))
[[ "$(value server_bad)" == 0 ]]
[[ "$(value host_bad)" == 0 ]]
[[ "$(value channel_bad)" == 0 ]]
[[ "$(value fping_bad)" == 0 ]]
[[ "$(value freshness_bad)" == 0 ]]
[[ "$(value unsupported_min)" == 2 ]]
[[ "$(value unsupported_max)" == 2 ]]

db_state="$(mariadb --protocol=socket --batch --raw --skip-column-names "${db_name}" -e "SELECT CONCAT(SUM(h.hostid IN (10873,10874) AND h.status=0),',',SUM(h.status=0),',',(SELECT SUM(status=0) FROM actions),',',(SELECT SUM(status=0) FROM media_type),',',(SELECT COALESCE(SUM(status=0),0) FROM connector)) FROM hosts h WHERE h.flags IN (0,4);")"
[[ ${db_state} == '2,2,0,0,0' ]]

systemctl disable --now ness-zabbix-pilot-sample.timer

evidence="${evidence_root}/zabbix-pilot-cavan-final-$(date +%Y%m%dT%H%M%S%z).txt"
{
  printf 'pilot_started_at=2026-08-29T17:59:56-03:00\n'
  printf 'pilot_completed_at=%s\n' "$(date --iso-8601=seconds)"
  printf '%s\n' "${stats}"
  printf 'db_state_pilot_total_actions_media_connectors=%s\n' "${db_state}"
  printf 'samples_sha256=%s\n' "$(sha256sum "${samples}" | awk '{print $1}')"
  printf 'known_failed_unit_samples=certbot-before-dns-only\n'
  printf 'pilot_result=PASS\n'
} >"${evidence}"
chmod 0600 "${evidence}"
cat "${evidence}"
