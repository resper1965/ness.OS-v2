#!/usr/bin/env bash
set -euo pipefail

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
SELECT "identity", u.id, u.name, u.is_active,
       COALESCE(GROUP_CONCAT(DISTINCT p.name ORDER BY p.name SEPARATOR ","), "no-profile")
FROM glpi_users u
LEFT JOIN glpi_profiles_users pu ON pu.users_id = u.id
LEFT JOIN glpi_profiles p ON p.id = pu.profiles_id
WHERE LOWER(u.name) IN ("resper", "iaraujo", "rsalerno", "agsilva")
   OR LOWER(u.name) LIKE "%ricardo%"
   OR LOWER(u.name) LIKE "%ismael%"
   OR LOWER(u.name) LIKE "%rogerio%"
   OR LOWER(u.name) LIKE "%rogério%"
   OR LOWER(u.name) LIKE "%agnaldo%"
GROUP BY u.id, u.name, u.is_active
ORDER BY u.name;

SELECT "profile", id, name, interface, is_default
FROM glpi_profiles
ORDER BY name;
SQL
'
unset DB_PASSWORD
