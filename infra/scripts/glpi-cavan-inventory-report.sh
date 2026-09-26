#!/usr/bin/env bash
set -euo pipefail

# Read-only reconciliation report for the Cavan pilot in GLPI.
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
SET @entity_id := (
  SELECT id FROM glpi_entities WHERE name = "Cavan" ORDER BY id LIMIT 1
);

SELECT "entity_id", COALESCE(@entity_id, -1);
SELECT "computers", COUNT(*) FROM glpi_computers
  WHERE entities_id = @entity_id AND is_deleted = 0;
SELECT "network_equipment", COUNT(*) FROM glpi_networkequipments
  WHERE entities_id = @entity_id AND is_deleted = 0;
SELECT "printers", COUNT(*) FROM glpi_printers
  WHERE entities_id = @entity_id AND is_deleted = 0;
SELECT "monitors", COUNT(*) FROM glpi_monitors
  WHERE entities_id = @entity_id AND is_deleted = 0;
SELECT "peripherals", COUNT(*) FROM glpi_peripherals
  WHERE entities_id = @entity_id AND is_deleted = 0;
SELECT "phones", COUNT(*) FROM glpi_phones
  WHERE entities_id = @entity_id AND is_deleted = 0;
SELECT "locations", COUNT(*) FROM glpi_locations
  WHERE entities_id = @entity_id;

SELECT "computer", c.id, c.name, COALESCE(c.serial, ""),
       COALESCE(c.otherserial, ""), COALESCE(l.completename, ""),
       COALESCE(m.name, ""), COALESCE(cm.name, "")
  FROM glpi_computers c
  LEFT JOIN glpi_locations l ON l.id = c.locations_id
  LEFT JOIN glpi_manufacturers m ON m.id = c.manufacturers_id
  LEFT JOIN glpi_computermodels cm ON cm.id = c.computermodels_id
 WHERE c.entities_id = @entity_id AND c.is_deleted = 0
 ORDER BY c.id;

SELECT "network_equipment", n.id, n.name, COALESCE(n.serial, ""),
       COALESCE(n.otherserial, ""), COALESCE(l.completename, ""),
       COALESCE(m.name, ""), COALESCE(nm.name, "")
  FROM glpi_networkequipments n
  LEFT JOIN glpi_locations l ON l.id = n.locations_id
  LEFT JOIN glpi_manufacturers m ON m.id = n.manufacturers_id
  LEFT JOIN glpi_networkequipmentmodels nm ON nm.id = n.networkequipmentmodels_id
 WHERE n.entities_id = @entity_id AND n.is_deleted = 0
 ORDER BY n.id;

SELECT "location", id, completename
  FROM glpi_locations
 WHERE entities_id = @entity_id
 ORDER BY id;

SELECT "manufacturer_lookup", id, name
  FROM glpi_manufacturers
 WHERE LOWER(name) REGEXP "aruba|hewlett|fortinet|cisco"
 ORDER BY name, id;

SELECT "network_model_lookup", id, name
  FROM glpi_networkequipmentmodels
 WHERE LOWER(name) REGEXP "aruba|cx|fortigate|catalyst"
 ORDER BY name, id;
SQL
'
unset DB_PASSWORD
