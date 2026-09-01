#!/usr/bin/env bash
set -euo pipefail

cd /opt/n-infraops

rollback_dir=/opt/n-infraops/change-backups/glpi-pin-20260821t123440-0300
install -d -m 0700 -o root -g root "${rollback_dir}"
docker cp ninf-glpi:/var/glpi/config/config_db.php "${rollback_dir}/config_db.php.pre-fix"
chmod 0600 "${rollback_dir}/config_db.php.pre-fix"

NEW_DB_PASSWORD="$(sed -n 's/^NINF_GLPI_DB_PASSWORD=//p' app/.env | tail -1)"
if [[ -z "${NEW_DB_PASSWORD}" ]]; then
  echo 'missing rotated GLPI password' >&2
  exit 1
fi
export NEW_DB_PASSWORD
docker exec -e NEW_DB_PASSWORD ninf-glpi php -r '
$p="/var/glpi/config/config_db.php";
$s=file_get_contents($p);
$escaped=str_replace(["\\\\", "\x27"], ["\\\\\\\\", "\\\\\x27"], getenv("NEW_DB_PASSWORD"));
$n=preg_replace_callback(
  "/(public[[:space:]]+\\\$dbpassword[[:space:]]*=[[:space:]]*)\x27[^\x27]*\x27;/",
  static fn($m) => $m[1]."\x27".$escaped."\x27;",
  $s,
  1,
  $count
);
if ($count !== 1 || file_put_contents($p,$n) === false) {
  fwrite(STDERR,"config update failed\n");
  exit(1);
}
'
unset NEW_DB_PASSWORD

docker restart ninf-glpi >/dev/null
status=000
for _ in $(seq 1 30); do
  status="$(docker exec ninf-glpi sh -lc 'curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1/' 2>/dev/null || true)"
  case "${status}" in
    200|301|302|303) break ;;
  esac
  sleep 2
done
printf 'glpi_http_inside=%s\n' "${status}"
case "${status}" in
  200|301|302|303) ;;
  *) exit 1 ;;
esac

DB_PASS="$(sed -n 's/^NINF_GLPI_DB_PASSWORD=//p' app/.env | tail -1)"
export DB_PASS
printf 'glpi_tables='
docker exec -e DB_PASS ninf-glpi-db sh -lc \
  'mariadb -uglpi -p"$DB_PASS" glpi -Nse "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE();"'
unset DB_PASS

printf 'cron_errors_recent='
docker logs --since 30s ninf-glpi 2>&1 \
  | grep -c 'connection to the SQL server could not be established' || true
printf 'rollback_file_mode='
stat -c '%a:%U:%G' "${rollback_dir}/config_db.php.pre-fix"
