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
SELECT "entities", COUNT(*) FROM glpi_entities;
SELECT "ticket_categories", COUNT(*) FROM glpi_itilcategories;
SELECT "ticket_templates", COUNT(*) FROM glpi_tickettemplates;
SELECT "projects", COUNT(*) FROM glpi_projects;
SELECT "project_tasks", COUNT(*) FROM glpi_projecttasks;
SELECT "knowledge_items", COUNT(*) FROM glpi_knowbaseitems;
SELECT "knowledge_categories", COUNT(*) FROM glpi_knowbaseitemcategories;
SELECT "service_levels", COUNT(*) FROM glpi_slas;

SELECT "entity", id, completename FROM glpi_entities ORDER BY id LIMIT 30;
SELECT "ticket_category", id, completename FROM glpi_itilcategories ORDER BY id LIMIT 40;
SELECT "project", id, name, projectstates_id FROM glpi_projects ORDER BY id LIMIT 30;
SELECT "knowledge_category", id, completename FROM glpi_knowbaseitemcategories ORDER BY id LIMIT 40;
SELECT "knowledge_item", id, name, is_faq FROM glpi_knowbaseitems ORDER BY id LIMIT 30;
SQL
'
unset DB_PASSWORD
