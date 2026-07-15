#!/bin/bash
export SSHPASS='lav9f1e5CICu!vyh'

sshpass -e ssh -o StrictHostKeyChecking=no -o KexAlgorithms=curve25519-sha256 -o IPQoS=none root@144.91.115.242 << 'ENDSSH'

echo "=== Check Auth.php line ~1450-1530 (isAlternateAuth) ==="
docker exec ninf-glpi sed -n '1450,1530p' /var/www/glpi/src/Auth.php

echo ""
echo "=== Check Auth.php line ~570-600 (getAlternateAuthSystemsUserLogin) ==="
docker exec ninf-glpi sed -n '570,600p' /var/www/glpi/src/Auth.php

echo ""
echo "=== Check login.php flow ==="
docker exec ninf-glpi cat /var/www/glpi/front/login.php

ENDSSH
