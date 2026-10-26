#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

if [[ ${EUID} -ne 0 ]]; then
  echo "This report must run as root." >&2
  exit 1
fi

readonly evidence="/root/incident-quarantine/20260820-zbx-sys-health/db-evidence/admin-auditlog-from-20260722.sql.gz"
readonly zabbix_config="/etc/zabbix/zabbix_server.conf"

[[ -r "${evidence}" ]] || { echo "Missing evidence: ${evidence}" >&2; exit 2; }
[[ -r "${zabbix_config}" ]] || { echo "Missing config: ${zabbix_config}" >&2; exit 3; }

mapfile -t host_ids < <(
  gzip -cd "${evidence}" \
    | grep -o 'script.hostid[^]]*' \
    | grep -o '[0-9][0-9]*' \
    | sort -n -u
)

(( ${#host_ids[@]} > 0 )) || { echo "No contextual host IDs found." >&2; exit 4; }

host_id_csv="$(IFS=,; echo "${host_ids[*]}")"
db_user="$(sed -n 's/^DBUser=//p' "${zabbix_config}" | tail -1)"
db_password="$(sed -n 's/^DBPassword=//p' "${zabbix_config}" | tail -1)"
db_name="$(sed -n 's/^DBName=//p' "${zabbix_config}" | tail -1)"

db_user="${db_user:-zabbix}"
db_name="${db_name:-zabbix}"
export MYSQL_PWD="${db_password}"

echo "CONTEXT_HOST_IDS=${host_id_csv}"
echo "EXECUTION_ROWS=$(gzip -cd "${evidence}" | grep -c 'script.hostid')"
echo "EXECUTIONS_BY_HOST_BEGIN"
for host_id in "${host_ids[@]}"; do
  count="$(gzip -cd "${evidence}" | grep -o 'script.hostid[^]]*' | grep -c "${host_id}" || true)"
  printf '%s\t%s\n' "${host_id}" "${count}"
done
echo "EXECUTIONS_BY_HOST_END"

echo "HOSTS_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT
      h.hostid,
      h.host,
      h.name,
      h.status,
      COALESCE(h.proxyid, 0),
      COALESCE(GROUP_CONCAT(CONCAT(i.type, ':', IF(i.useip=1, i.ip, i.dns), ':', i.port, ':avail=', i.available) ORDER BY i.main DESC, i.type SEPARATOR ';'), 'no-interface')
    FROM hosts h
    LEFT JOIN interface i ON i.hostid=h.hostid
    WHERE h.hostid IN (${host_id_csv})
    GROUP BY h.hostid,h.host,h.name,h.status,h.proxyid
    ORDER BY h.hostid;"
echo "HOSTS_END"

echo "INVENTORY_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT
      h.hostid,
      COALESCE(NULLIF(hi.name,''), '-'),
      COALESCE(NULLIF(hi.type,''), '-'),
      COALESCE(NULLIF(hi.os,''), '-'),
      COALESCE(NULLIF(hi.location,''), '-'),
      COALESCE(NULLIF(hi.site_city,''), '-')
    FROM hosts h
    LEFT JOIN host_inventory hi ON hi.hostid=h.hostid
    WHERE h.hostid IN (${host_id_csv})
    ORDER BY h.hostid;"
echo "INVENTORY_END"

echo "SYSTEM_TELEMETRY_COVERAGE_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT
      h.hostid,
      SUM(i.key_ LIKE 'system.uname%'),
      SUM(i.key_ LIKE 'system.sw.os%'),
      SUM(i.key_ LIKE 'proc.num%'),
      SUM(i.key_ LIKE 'system.run%')
    FROM hosts h
    LEFT JOIN items i ON i.hostid=h.hostid AND i.flags<>2
    WHERE h.hostid IN (${host_id_csv})
    GROUP BY h.hostid
    ORDER BY h.hostid;"
echo "SYSTEM_TELEMETRY_COVERAGE_END"

echo "SYSTEM_IDENTITY_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT
      i.hostid,
      i.key_,
      FROM_UNIXTIME((SELECT hs.clock FROM history_str hs WHERE hs.itemid=i.itemid ORDER BY hs.clock DESC LIMIT 1)),
      LEFT((SELECT hs.value FROM history_str hs WHERE hs.itemid=i.itemid ORDER BY hs.clock DESC LIMIT 1), 240)
    FROM items i
    WHERE i.hostid IN (${host_id_csv})
      AND (i.key_='system.uname' OR i.key_ LIKE 'system.sw.os%')
    ORDER BY i.hostid,i.key_;"
echo "SYSTEM_IDENTITY_END"

echo "PROCESS_ITEMS_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT i.hostid,i.key_,i.name,i.status,COALESCE(ir.state,0),COALESCE(ir.error,'')
    FROM items i
    LEFT JOIN item_rtdata ir ON ir.itemid=i.itemid
    WHERE i.hostid IN (${host_id_csv}) AND i.key_ LIKE 'proc.num%'
    ORDER BY i.hostid,i.itemid;"
echo "PROCESS_ITEMS_END"

echo "MONITORING_HEALTH_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT
      h.hostid,
      COUNT(i.itemid),
      SUM(i.status=0),
      SUM(i.status=1),
      SUM(CASE WHEN ir.state=1 THEN 1 ELSE 0 END)
    FROM hosts h
    LEFT JOIN items i ON i.hostid=h.hostid AND i.flags<>2
    LEFT JOIN item_rtdata ir ON ir.itemid=i.itemid
    WHERE h.hostid IN (${host_id_csv})
    GROUP BY h.hostid
    ORDER BY h.hostid;"
echo "MONITORING_HEALTH_END"

echo "PROXIES_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT
      p.proxyid,
      p.name,
      p.operating_mode,
      FROM_UNIXTIME(pr.lastaccess),
      pr.version
    FROM proxy p
    LEFT JOIN proxy_rtdata pr ON pr.proxyid=p.proxyid
    WHERE p.proxyid IN (
      SELECT DISTINCT h.proxyid
      FROM hosts h
      WHERE h.hostid IN (${host_id_csv}) AND h.proxyid IS NOT NULL
    )
    ORDER BY p.proxyid;"
echo "PROXIES_END"

unset MYSQL_PWD db_password
