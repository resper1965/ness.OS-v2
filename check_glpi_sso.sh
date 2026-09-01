#!/usr/bin/env bash
set -Eeuo pipefail

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes ness_admin@144.91.115.242 << 'ENDSSH'

echo "=== Check Auth.php line ~1450-1530 (isAlternateAuth) ==="
sudo docker exec ninf-glpi sed -n '1450,1530p' /var/www/glpi/src/Auth.php

echo ""
echo "=== Check Auth.php line ~570-600 (getAlternateAuthSystemsUserLogin) ==="
sudo docker exec ninf-glpi sed -n '570,600p' /var/www/glpi/src/Auth.php

echo ""
echo "=== Check login.php flow ==="
sudo docker exec ninf-glpi cat /var/www/glpi/front/login.php

ENDSSH
