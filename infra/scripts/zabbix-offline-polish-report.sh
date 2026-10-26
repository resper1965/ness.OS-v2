#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

readonly db_name="dbzabbix"
readonly evidence_root="/var/lib/ness-os/restore-evidence"
readonly report="${evidence_root}/offline-polish-baseline-$(date +%Y%m%dT%H%M%S%z).txt"

[[ ${EUID} -eq 0 ]] || { echo "run as root" >&2; exit 1; }
[[ "$(systemctl is-active mariadb 2>/dev/null || true)" == active ]] || exit 2
[[ "$(systemctl is-active zabbix-server 2>/dev/null || true)" == inactive ]] || exit 3
[[ "$(systemctl is-enabled zabbix-server 2>/dev/null || true)" == masked ]] || exit 4
ss -H -lnt 'sport = :10051' | grep -q . && exit 5

runtime_columns="$(mariadb --protocol=socket --batch --raw --skip-column-names information_schema -e \
  "SELECT COUNT(*) FROM columns WHERE table_schema='dbzabbix' AND table_name='item_rtdata' AND column_name IN ('itemid','state','error');")"
[[ "${runtime_columns}" == 3 ]] || exit 6

sql() {
  mariadb --protocol=socket --batch --raw --skip-column-names "${db_name}" -e "$1"
}

scalar() {
  local name="$1" query="$2"
  printf '%s=' "${name}"
  sql "${query}"
}

{
  printf 'generated_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'database=%s\n' "${db_name}"
  printf 'zabbix_server=inactive-masked\n'
  printf 'collection_listener_10051=absent\n'

  scalar monitored_hosts \
    "SELECT COUNT(*) FROM hosts WHERE status=0;"
  scalar templates \
    "SELECT COUNT(*) FROM hosts WHERE status=3;"
  scalar enabled_items_monitored_hosts \
    "SELECT COUNT(*) FROM items i JOIN hosts h ON h.hostid=i.hostid WHERE i.status=0 AND h.status=0;"
  scalar unsupported_items_monitored_hosts \
    "SELECT COUNT(*) FROM items i JOIN item_rtdata rt ON rt.itemid=i.itemid JOIN hosts h ON h.hostid=i.hostid WHERE i.status=0 AND rt.state=1 AND h.status=0;"
  scalar enabled_unknown_triggers_monitored_hosts \
    "SELECT COUNT(DISTINCT t.triggerid) FROM triggers t JOIN functions f ON f.triggerid=t.triggerid JOIN items i ON i.itemid=f.itemid JOIN hosts h ON h.hostid=i.hostid WHERE t.status=0 AND t.state=1 AND h.status=0;"
  scalar escalations_total \
    "SELECT COUNT(*) FROM escalations;"
  scalar escalations_nextcheck_zero \
    "SELECT COUNT(*) FROM escalations WHERE nextcheck=0;"
  scalar escalations_overdue_nonzero \
    "SELECT COUNT(*) FROM escalations WHERE nextcheck>0 AND nextcheck<UNIX_TIMESTAMP();"
  scalar monitored_hosts_without_template \
    "SELECT COUNT(*) FROM hosts h WHERE h.status=0 AND NOT EXISTS (SELECT 1 FROM hosts_templates ht WHERE ht.hostid=h.hostid);"
  scalar monitored_hosts_without_tag \
    "SELECT COUNT(*) FROM hosts h WHERE h.status=0 AND NOT EXISTS (SELECT 1 FROM host_tag t WHERE t.hostid=h.hostid);"
  scalar monitored_hosts_with_coordinates \
    "SELECT COUNT(*) FROM hosts h JOIN host_inventory hi ON hi.hostid=h.hostid WHERE h.status=0 AND hi.location_lat<>'' AND hi.location_lon<>'';"
  scalar maps \
    "SELECT COUNT(*) FROM sysmaps;"
  scalar map_elements \
    "SELECT COUNT(*) FROM sysmaps_elements;"
  scalar active_actions \
    "SELECT COUNT(*) FROM actions WHERE status=0;"
  scalar enabled_media_types \
    "SELECT COUNT(*) FROM media_type WHERE status=0;"
  scalar enabled_connectors \
    "SELECT IF(EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='dbzabbix' AND table_name='connector'), (SELECT COUNT(*) FROM connector WHERE status=0), 0);"
  scalar database_bytes \
    "SELECT COALESCE(SUM(data_length+index_length),0) FROM information_schema.tables WHERE table_schema='dbzabbix';"

  printf '\n[unsupported_by_safe_category]\n'
  sql "SELECT CASE
      WHEN LOWER(rt.error) REGEXP 'timeout|timed out' THEN 'timeout'
      WHEN LOWER(rt.error) REGEXP 'auth|unauthorized|login|credential|password' THEN 'authentication'
      WHEN LOWER(rt.error) REGEXP 'preprocess|jsonpath|xpath|javascript' THEN 'preprocessing'
      WHEN LOWER(rt.error) REGEXP 'dns|resolve|network|connect|unreachable|no route' THEN 'connectivity_dns'
      WHEN LOWER(rt.error) REGEXP 'calculated|formula|expression|division by zero' THEN 'calculation_expression'
      WHEN LOWER(rt.error) REGEXP 'unknown metric|unsupported key|invalid key|oid|snmp' THEN 'key_metric_oid'
      WHEN LOWER(rt.error) REGEXP 'value type|type of value|cannot convert' THEN 'value_type'
      ELSE 'other'
    END AS category, COUNT(*)
    FROM items i JOIN item_rtdata rt ON rt.itemid=i.itemid JOIN hosts h ON h.hostid=i.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
    GROUP BY category ORDER BY COUNT(*) DESC, category;"

  printf '\n[top_unsupported_hosts]\n'
  sql "SELECT h.hostid, h.host, COUNT(*)
    FROM items i JOIN item_rtdata rt ON rt.itemid=i.itemid JOIN hosts h ON h.hostid=i.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
    GROUP BY h.hostid,h.host ORDER BY COUNT(*) DESC,h.hostid LIMIT 20;"

  printf '\n[top_unsupported_source_templates]\n'
  sql "SELECT COALESCE(th.host,'local_or_discovered'), COUNT(*)
    FROM items i
    JOIN item_rtdata rt ON rt.itemid=i.itemid
    JOIN hosts h ON h.hostid=i.hostid
    LEFT JOIN items ti ON ti.itemid=i.templateid
    LEFT JOIN hosts th ON th.hostid=ti.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
    GROUP BY COALESCE(th.host,'local_or_discovered')
    ORDER BY COUNT(*) DESC LIMIT 20;"

  printf '\n[unsupported_template_category_matrix]\n'
  sql "SELECT COALESCE(th.host,'local_or_discovered'),
    CASE
      WHEN LOWER(rt.error) REGEXP 'timeout|timed out' THEN 'timeout'
      WHEN LOWER(rt.error) REGEXP 'auth|unauthorized|login|credential|password' THEN 'authentication'
      WHEN LOWER(rt.error) REGEXP 'preprocess|jsonpath|xpath|javascript' THEN 'preprocessing'
      WHEN LOWER(rt.error) REGEXP 'dns|resolve|network|connect|unreachable|no route' THEN 'connectivity_dns'
      WHEN LOWER(rt.error) REGEXP 'calculated|formula|expression|division by zero' THEN 'calculation_expression'
      WHEN LOWER(rt.error) REGEXP 'unknown metric|unsupported key|invalid key|oid|snmp' THEN 'key_metric_oid'
      WHEN LOWER(rt.error) REGEXP 'value type|type of value|cannot convert' THEN 'value_type'
      ELSE 'other'
    END AS category, COUNT(*)
    FROM items i
    JOIN item_rtdata rt ON rt.itemid=i.itemid
    JOIN hosts h ON h.hostid=i.hostid
    LEFT JOIN items ti ON ti.itemid=i.templateid
    LEFT JOIN hosts th ON th.hostid=ti.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
    GROUP BY COALESCE(th.host,'local_or_discovered'),category
    ORDER BY COUNT(*) DESC,COALESCE(th.host,'local_or_discovered'),category
    LIMIT 50;"

  printf '\n[unsupported_item_types]\n'
  sql "SELECT i.type, COUNT(*)
    FROM items i JOIN item_rtdata rt ON rt.itemid=i.itemid JOIN hosts h ON h.hostid=i.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
    GROUP BY i.type ORDER BY COUNT(*) DESC,i.type;"

  printf '\n[safe_error_predicate_counts]\n'
  sql "SELECT 'performance_counter',SUM(LOWER(rt.error) REGEXP 'performance counter|pdh') FROM item_rtdata rt JOIN items i ON i.itemid=rt.itemid JOIN hosts h ON h.hostid=i.hostid WHERE rt.state=1 AND i.status=0 AND h.status=0
    UNION ALL SELECT 'wmi',SUM(LOWER(rt.error) REGEXP 'wmi|windows management instrumentation') FROM item_rtdata rt JOIN items i ON i.itemid=rt.itemid JOIN hosts h ON h.hostid=i.hostid WHERE rt.state=1 AND i.status=0 AND h.status=0
    UNION ALL SELECT 'invalid_parameter',SUM(LOWER(rt.error) REGEXP 'invalid parameter|incorrect parameter') FROM item_rtdata rt JOIN items i ON i.itemid=rt.itemid JOIN hosts h ON h.hostid=i.hostid WHERE rt.state=1 AND i.status=0 AND h.status=0
    UNION ALL SELECT 'not_found',SUM(LOWER(rt.error) REGEXP 'not found|cannot find|does not exist|no such') FROM item_rtdata rt JOIN items i ON i.itemid=rt.itemid JOIN hosts h ON h.hostid=i.hostid WHERE rt.state=1 AND i.status=0 AND h.status=0
    UNION ALL SELECT 'not_available',SUM(LOWER(rt.error) REGEXP 'not available|unavailable') FROM item_rtdata rt JOIN items i ON i.itemid=rt.itemid JOIN hosts h ON h.hostid=i.hostid WHERE rt.state=1 AND i.status=0 AND h.status=0
    UNION ALL SELECT 'failed_to_execute',SUM(LOWER(rt.error) REGEXP 'failed to execute|cannot execute') FROM item_rtdata rt JOIN items i ON i.itemid=rt.itemid JOIN hosts h ON h.hostid=i.hostid WHERE rt.state=1 AND i.status=0 AND h.status=0
    UNION ALL SELECT 'vmware_service',SUM(LOWER(rt.error) REGEXP 'vmware service|vmware collector|virtual machine|hypervisor') FROM item_rtdata rt JOIN items i ON i.itemid=rt.itemid JOIN hosts h ON h.hostid=i.hostid WHERE rt.state=1 AND i.status=0 AND h.status=0
    UNION ALL SELECT 'empty_result',SUM(LOWER(rt.error) REGEXP 'empty result|returned no data|no data') FROM item_rtdata rt JOIN items i ON i.itemid=rt.itemid JOIN hosts h ON h.hostid=i.hostid WHERE rt.state=1 AND i.status=0 AND h.status=0
    UNION ALL SELECT 'macro_or_url',SUM(LOWER(rt.error) REGEXP 'macro|url') FROM item_rtdata rt JOIN items i ON i.itemid=rt.itemid JOIN hosts h ON h.hostid=i.hostid WHERE rt.state=1 AND i.status=0 AND h.status=0
    UNION ALL SELECT 'division_by_zero',SUM(LOWER(rt.error) REGEXP 'division by zero|divide by zero') FROM item_rtdata rt JOIN items i ON i.itemid=rt.itemid JOIN hosts h ON h.hostid=i.hostid WHERE rt.state=1 AND i.status=0 AND h.status=0;"

  printf '\n[wave_a_fortigate_calculation_candidates]\n'
  sql "SELECT COALESCE(ti.itemid,i.itemid),COALESCE(ti.name,i.name),COALESCE(ti.key_,i.key_),COUNT(*)
    FROM items i
    JOIN item_rtdata rt ON rt.itemid=i.itemid
    JOIN hosts h ON h.hostid=i.hostid
    LEFT JOIN items ti ON ti.itemid=i.templateid
    LEFT JOIN hosts th ON th.hostid=ti.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
      AND th.host='FortiGate by SNMP'
      AND LOWER(rt.error) REGEXP 'calculated|formula|expression|division by zero|divide by zero'
    GROUP BY COALESCE(ti.itemid,i.itemid),COALESCE(ti.name,i.name),COALESCE(ti.key_,i.key_)
    ORDER BY COUNT(*) DESC,COALESCE(ti.itemid,i.itemid);"

  printf '\n[wave_a_fortigate_affected_assets]\n'
  sql "SELECT h.hostid,h.host,
      COALESCE(NULLIF(hi.vendor,''),'unknown') AS vendor,
      COALESCE(NULLIF(hi.model,''),'unknown') AS model,
      COUNT(*)
    FROM items i
    JOIN item_rtdata rt ON rt.itemid=i.itemid
    JOIN hosts h ON h.hostid=i.hostid
    LEFT JOIN host_inventory hi ON hi.hostid=h.hostid
    LEFT JOIN items ti ON ti.itemid=i.templateid
    LEFT JOIN hosts th ON th.hostid=ti.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
      AND th.host='FortiGate by SNMP'
      AND i.key_='vfs.fs.pfree'
      AND LOWER(rt.error) REGEXP 'calculated|formula|expression|division by zero|divide by zero'
    GROUP BY h.hostid,h.host,hi.vendor,hi.model
    ORDER BY h.host;"

  printf '\n[wave_a_fortigate_canonical_device_candidates]\n'
  sql "SELECT TRIM(SUBSTRING_INDEX(h.host,' Link ',1)) AS canonical_device,COUNT(DISTINCT h.hostid)
    FROM items i
    JOIN item_rtdata rt ON rt.itemid=i.itemid
    JOIN hosts h ON h.hostid=i.hostid
    LEFT JOIN items ti ON ti.itemid=i.templateid
    LEFT JOIN hosts th ON th.hostid=ti.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
      AND th.host='FortiGate by SNMP'
      AND i.key_='vfs.fs.pfree'
      AND LOWER(rt.error) REGEXP 'calculated|formula|expression|division by zero|divide by zero'
    GROUP BY canonical_device
    ORDER BY COUNT(DISTINCT h.hostid) DESC,canonical_device;"

  printf '\n[wave_b_fortigate_http_candidates]\n'
  sql "SELECT COALESCE(ti.itemid,i.itemid),COALESCE(ti.name,i.name),COALESCE(ti.key_,i.key_),COUNT(*)
    FROM items i
    JOIN item_rtdata rt ON rt.itemid=i.itemid
    JOIN hosts h ON h.hostid=i.hostid
    LEFT JOIN items ti ON ti.itemid=i.templateid
    LEFT JOIN hosts th ON th.hostid=ti.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
      AND th.host='FortiGate by HTTP'
      AND LOWER(rt.error) REGEXP 'preprocess|jsonpath|xpath|javascript'
    GROUP BY COALESCE(ti.itemid,i.itemid),COALESCE(ti.name,i.name),COALESCE(ti.key_,i.key_)
    ORDER BY COUNT(*) DESC,COALESCE(ti.itemid,i.itemid)
    LIMIT 30;"

  printf '\n[wave_b_fortigate_http_affected_assets]\n'
  sql "SELECT h.hostid,h.host,COUNT(*)
    FROM items i
    JOIN item_rtdata rt ON rt.itemid=i.itemid
    JOIN hosts h ON h.hostid=i.hostid
    LEFT JOIN items ti ON ti.itemid=i.templateid
    LEFT JOIN hosts th ON th.hostid=ti.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
      AND th.host='FortiGate by HTTP'
      AND LOWER(rt.error) REGEXP 'preprocess|jsonpath|xpath|javascript'
    GROUP BY h.hostid,h.host
    ORDER BY COUNT(*) DESC,h.host;"

  printf '\n[wave_b_affected_asset_template_links]\n'
  sql "SELECT h.hostid,h.host,GROUP_CONCAT(DISTINCT linked.host ORDER BY linked.host SEPARATOR ',')
    FROM hosts h
    JOIN hosts_templates ht ON ht.hostid=h.hostid
    JOIN hosts linked ON linked.hostid=ht.templateid
    WHERE h.hostid IN (
      SELECT DISTINCT i.hostid
      FROM items i
      JOIN item_rtdata rt ON rt.itemid=i.itemid
      LEFT JOIN items ti ON ti.itemid=i.templateid
      LEFT JOIN hosts th ON th.hostid=ti.hostid
      WHERE i.status=0 AND rt.state=1
        AND th.host='FortiGate by HTTP'
        AND LOWER(rt.error) REGEXP 'preprocess|jsonpath|xpath|javascript'
    )
    GROUP BY h.hostid,h.host
    ORDER BY h.host;"

  printf '\n[wave_d_windows_candidates]\n'
  sql "SELECT COALESCE(ti.itemid,i.itemid),COALESCE(ti.name,i.name),COALESCE(ti.key_,i.key_),COUNT(*)
    FROM items i
    JOIN item_rtdata rt ON rt.itemid=i.itemid
    JOIN hosts h ON h.hostid=i.hostid
    LEFT JOIN items ti ON ti.itemid=i.templateid
    LEFT JOIN hosts th ON th.hostid=ti.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
      AND th.host='Windows by Zabbix agent'
    GROUP BY COALESCE(ti.itemid,i.itemid),COALESCE(ti.name,i.name),COALESCE(ti.key_,i.key_)
    ORDER BY COUNT(*) DESC,COALESCE(ti.itemid,i.itemid)
    LIMIT 30;"

  printf '\n[wave_d_windows_scope]\n'
  sql "SELECT COUNT(DISTINCT h.hostid) AS affected_hosts,COUNT(*) AS unsupported_items
    FROM items i
    JOIN item_rtdata rt ON rt.itemid=i.itemid
    JOIN hosts h ON h.hostid=i.hostid
    LEFT JOIN items ti ON ti.itemid=i.templateid
    LEFT JOIN hosts th ON th.hostid=ti.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
      AND th.host='Windows by Zabbix agent';"

  printf '\n[wave_d_windows_agent_availability]\n'
  sql "SELECT hi.available,COUNT(DISTINCT h.hostid)
    FROM items i
    JOIN item_rtdata rt ON rt.itemid=i.itemid
    JOIN hosts h ON h.hostid=i.hostid
    JOIN interface hi ON hi.hostid=h.hostid AND hi.type=1 AND hi.main=1
    LEFT JOIN items ti ON ti.itemid=i.templateid
    LEFT JOIN hosts th ON th.hostid=ti.hostid
    WHERE i.status=0 AND rt.state=1 AND h.status=0
      AND th.host='Windows by Zabbix agent'
    GROUP BY hi.available
    ORDER BY hi.available;"

  printf '\n[escalations_by_action]\n'
  sql "SELECT e.actionid, COALESCE(a.name,'missing_action'), COUNT(*)
    FROM escalations e LEFT JOIN actions a ON a.actionid=e.actionid
    GROUP BY e.actionid,a.name ORDER BY COUNT(*) DESC LIMIT 20;"
} >"${report}"

chmod 0600 "${report}"
printf 'offline polish baseline: PASS report=%s\n' "${report}"
