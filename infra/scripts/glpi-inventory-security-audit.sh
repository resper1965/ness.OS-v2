#!/usr/bin/env bash
set -euo pipefail

# Read-only triage for the historical native-inventory scanner records.
cd /opt/n-infraops
db_password="$(sed -n 's/^NINF_GLPI_DB_PASSWORD=//p' app/.env | tail -1)"
if [[ -z "${db_password}" ]]; then
    echo 'NINF_GLPI_DB_PASSWORD is not configured' >&2
    exit 1
fi
export DB_PASSWORD="${db_password}"
unset db_password

docker exec -e DB_PASSWORD ninf-glpi-db sh -lc '
  mariadb -uglpi -p"$DB_PASSWORD" glpi --batch --skip-column-names <<"SQL"
SELECT "inventory_enabled", value
  FROM glpi_configs
 WHERE context = "inventory" AND name = "enabled_inventory";
SELECT "agent_total", COUNT(*) FROM glpi_agents;
SELECT "scanner_pattern_agents", COUNT(*)
  FROM glpi_agents
 WHERE name LIKE "%SLEEP(%" OR deviceid LIKE "%SLEEP(%";
SELECT "scanner_agents_linked_to_asset", COUNT(*)
  FROM glpi_agents
 WHERE (name LIKE "%SLEEP(%" OR deviceid LIKE "%SLEEP(%")
   AND (items_id <> 0 OR itemtype <> "Computer");
SELECT "scanner_first_last_contact", MIN(last_contact), MAX(last_contact)
  FROM glpi_agents
 WHERE name LIKE "%SLEEP(%" OR deviceid LIKE "%SLEEP(%";
SELECT "scanner_pattern_computers", COUNT(*)
  FROM glpi_computers
 WHERE name LIKE "%SLEEP(%" OR serial LIKE "%SLEEP(%";
SELECT "scanner_pattern_users", COUNT(*)
  FROM glpi_users
 WHERE name LIKE "%SLEEP(%" OR realname LIKE "%SLEEP(%"
    OR firstname LIKE "%SLEEP(%";
SELECT "scanner_pattern_logs", COUNT(*)
  FROM glpi_logs
 WHERE old_value LIKE "%SLEEP(%" OR new_value LIKE "%SLEEP(%";
SELECT "assets_created_during_window", "computer", COUNT(*)
  FROM glpi_computers
 WHERE date_creation >= "2026-07-15" AND date_creation < "2026-07-28"
UNION ALL
SELECT "assets_created_during_window", "network_equipment", COUNT(*)
  FROM glpi_networkequipments
 WHERE date_creation >= "2026-07-15" AND date_creation < "2026-07-28";
SQL
'
unset DB_PASSWORD
