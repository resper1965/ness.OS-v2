#!/usr/bin/env bash
set -euo pipefail

# Read-only GLPI native inventory readiness report. It never submits inventory.
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
SELECT "inventory_config", context, name, value
  FROM glpi_configs
 WHERE context = "inventory" OR name LIKE "%inventory%"
 ORDER BY context, name;
SELECT "agent_rows", COUNT(*) FROM glpi_agents;
SELECT "refused_equipment", COUNT(*) FROM glpi_refusedequipments;
SELECT "agent", id, name, deviceid, entities_id, itemtype, items_id,
       COALESCE(last_contact, ""), COALESCE(version, ""), COALESCE(tag, ""),
       COALESCE(remote_addr, ""), use_module_computer_inventory,
       use_module_network_discovery, use_module_network_inventory,
       use_module_package_deployment
  FROM glpi_agents
 ORDER BY id;
SELECT "agent_column", column_name
  FROM information_schema.columns
 WHERE table_schema = DATABASE() AND table_name = "glpi_agents"
 ORDER BY ordinal_position;
SQL
'
unset DB_PASSWORD

docker exec -i ninf-api python - <<'PY'
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

for path in ("/Inventory", "/front/inventory.php"):
    request = Request(f"http://ninf-glpi{path}", method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            status = response.status
            content_type = response.headers.get_content_type()
    except HTTPError as error:
        status = error.code
        content_type = error.headers.get_content_type()
    except URLError as error:
        print(json.dumps({"path": path, "transport_error": type(error).__name__}))
        continue
    print(json.dumps({"path": path, "status": status, "content_type": content_type}))
PY
