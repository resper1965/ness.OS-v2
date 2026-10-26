#!/usr/bin/env bash
# Usage: lab.sh up|down. Synthetic data only; never point this at production.
set -euo pipefail
cd "$(dirname "$0")"
LAB_DIR=${GLPI_LAB_DIR:-/tmp/opencode/glpi-lab}
export NINF_API_IMAGE=${NINF_API_IMAGE:-ness-api-lab:local}
export NESS_GLPI_MAINTENANCE_SUBNET=172.30.250.0/28
export NESS_GLPI_MAINTENANCE_GATEWAY_IP=172.30.250.3
export NESS_GLPI_MAINTENANCE_APP_TOKEN_FILE=$LAB_DIR/app_token
export NESS_GLPI_MAINTENANCE_USER_TOKEN_FILE=$LAB_DIR/user_token
export NESS_GLPI_MAINTENANCE_BEARER_FILE=$LAB_DIR/bearer
export NESS_GLPI_MAINTENANCE_APPROVED_IDS=${NESS_GLPI_MAINTENANCE_APPROVED_IDS:-1}
dc() { docker compose -f docker-compose.yml -f ../../../app/docker-compose.glpi-maintenance.yml "$@"; }

case ${1:-} in
down) dc down -v --remove-orphans; rm -rf "$LAB_DIR"; exit ;;
up) ;;
*) echo "usage: $0 up|down" >&2; exit 2 ;;
esac

docker image inspect "$NINF_API_IMAGE" >/dev/null 2>&1 || docker build -q -f ../../../app/Dockerfile -t "$NINF_API_IMAGE" ../../../app
umask 077; mkdir -p "$LAB_DIR"
for f in app_token user_token bearer; do [ -s "$LAB_DIR/$f" ] || openssl rand -hex 20 | tr -d '\n' >"$LAB_DIR/$f"; done

dc up -d --wait glpi-db glpi
until docker exec ness-glpi-lab-glpi curl -fsS -o /dev/null http://127.0.0.1/; do sleep 3; done
cli() { docker exec -u www-data -w /var/www/glpi ness-glpi-lab-glpi php bin/console "$@"; }
cli config:set enable_api 1 -q
cli config:set enable_api_login_credentials 1 -q
cli config:set enable_api_login_external_token 1 -q
sql() { dc exec -T glpi-db mariadb -uroot -plab-root-only glpi -e "$1"; }

if [ ! -s "$LAB_DIR/ids.json" ]; then
  docker exec -i -e APP_TOKEN="$(cat "$LAB_DIR/app_token")" -e GATEWAY_IP="$NESS_GLPI_MAINTENANCE_GATEWAY_IP" ness-glpi-lab-glpi python3 - <"seed.py" >"$LAB_DIR/ids.json"
  uid=$(python3 -c "import json;print(json.load(open('$LAB_DIR/ids.json'))['user'])")
  pid=$(python3 -c "import json;print(json.load(open('$LAB_DIR/ids.json'))['profile'])")
  # GLPI stores API tokens encrypted with its own key.
  enc=$(docker exec -u www-data ness-glpi-lab-glpi php -r 'require "/var/www/glpi/vendor/autoload.php"; echo (new GLPIKey("/var/glpi/config"))->encrypt($argv[1]);' "$(cat "$LAB_DIR/user_token")")
  sql "UPDATE glpi_users SET api_token='$enc' WHERE id=$uid;
       DELETE FROM glpi_profiles_users WHERE users_id=$uid AND profiles_id<>$pid;
       UPDATE glpi_profilerights SET rights=1 WHERE profiles_id=$pid AND name IN ('computer','ticket','document');"
fi
# Misconfigured allowlist on purpose: it also approves the entity-5 Computer, so only the server-side entity check can deny it.
export NESS_GLPI_MAINTENANCE_APPROVED_IDS=$(python3 -c "import json;d=json.load(open('$LAB_DIR/ids.json'));print(d['1']['Computer'],d['5']['Computer'],sep=',')")
dc up -d --wait glpi-maintenance-gateway hub
echo "lab ready: gateway http://127.0.0.1:18000 glpi http://127.0.0.1:18080 ids in $LAB_DIR/ids.json"
