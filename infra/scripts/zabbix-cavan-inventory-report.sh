#!/usr/bin/env bash
set -euo pipefail

# Read-only inventory reconciliation for the Cavan Matriz pilot.
[[ ${EUID} -eq 0 ]] || {
    echo 'must run as root' >&2
    exit 1
}

readonly zabbix_config=/etc/zabbix/zabbix_server.conf
db_user="$(sed -n 's/^DBUser=//p' "${zabbix_config}" | tail -1)"
db_password="$(sed -n 's/^DBPassword=//p' "${zabbix_config}" | tail -1)"
db_name="$(sed -n 's/^DBName=//p' "${zabbix_config}" | tail -1)"
db_user="${db_user:-zabbix}"
db_name="${db_name:-zabbix}"
export MYSQL_PWD="${db_password}"
unset db_password

mariadb --protocol=socket --batch --raw --skip-column-names \
    --user="${db_user}" --database="${db_name}" <<'SQL'
SELECT 'host_count', COUNT(DISTINCT h.hostid)
  FROM hosts h
  JOIN host_tag tenant
    ON tenant.hostid = h.hostid
   AND tenant.tag = 'tenant'
   AND tenant.value = 'cavan'
  JOIN host_tag site
    ON site.hostid = h.hostid
   AND site.tag = 'site'
   AND site.value = 'matriz-sp'
 WHERE h.flags IN (0, 4);

SELECT 'proxy', p.proxyid, p.name, FROM_UNIXTIME(pr.lastaccess)
  FROM proxy p
  LEFT JOIN proxy_rtdata pr ON pr.proxyid = p.proxyid
 WHERE p.proxyid = 4 OR p.name LIKE '%cav%'
 ORDER BY p.proxyid;

SELECT
    'host',
    h.hostid,
    h.name,
    h.status,
    COALESCE(p.name, ''),
    COALESCE(GROUP_CONCAT(
        DISTINCT CONCAT(
            CASE i.type
                WHEN 1 THEN 'agent'
                WHEN 2 THEN 'snmp'
                WHEN 3 THEN 'ipmi'
                WHEN 4 THEN 'jmx'
                ELSE CONCAT('type-', i.type)
            END,
            ':', IF(i.useip = 1, i.ip, i.dns), ':', i.port
        ) ORDER BY i.main DESC, i.type SEPARATOR ';'
    ), ''),
    COALESCE(NULLIF(hi.type, ''), ''),
    COALESCE(NULLIF(hi.vendor, ''), ''),
    COALESCE(NULLIF(hi.model, ''), ''),
    COALESCE(NULLIF(hi.serialno_a, ''), ''),
    COALESCE(NULLIF(hi.location, ''), ''),
    COALESCE(NULLIF(hi.site_city, ''), ''),
    COALESCE(GROUP_CONCAT(
        DISTINCT CONCAT(t.tag, '=', t.value)
        ORDER BY t.tag SEPARATOR ';'
    ), '')
  FROM hosts h
  JOIN host_tag tenant
    ON tenant.hostid = h.hostid
   AND tenant.tag = 'tenant'
   AND tenant.value = 'cavan'
  JOIN host_tag site
    ON site.hostid = h.hostid
   AND site.tag = 'site'
   AND site.value = 'matriz-sp'
  LEFT JOIN proxy p ON p.proxyid = h.proxyid
  LEFT JOIN interface i ON i.hostid = h.hostid
  LEFT JOIN host_inventory hi ON hi.hostid = h.hostid
  LEFT JOIN host_tag t ON t.hostid = h.hostid
 WHERE h.flags IN (0, 4)
 GROUP BY h.hostid, h.name, h.status, p.name, hi.type, hi.vendor, hi.model,
          hi.serialno_a, hi.location, hi.site_city
 ORDER BY h.hostid;
SQL

unset MYSQL_PWD
