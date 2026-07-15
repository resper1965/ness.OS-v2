#!/bin/bash
sshpass -p "lav9f1e5CICu!vyh" ssh -o StrictHostKeyChecking=no root@144.91.115.242 "docker exec ninf-glpi-db mysql -u glpi --password=glpi_pass_nessops_2026 glpi -e 'SELECT id, name, entities_id FROM glpi_entities;'"
