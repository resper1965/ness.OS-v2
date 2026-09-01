#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
input_file="${1:-}"
input_root=/opt/n-infraops/restore-input
mariadb_image='mariadb:10.11@sha256:be981e4113326ada8d6004174dd09eeaefc03094037f811182a52d4f2e737350'

[[ -n "${input_file}" && -f "${input_file}" ]]
resolved_input="$(realpath "${input_file}")"
case "${resolved_input}" in
  "${input_root}"/*) ;;
  *) echo "restore input must be below ${input_root}" >&2; exit 2 ;;
esac

gzip -t "${resolved_input}"
run_id="$(date +%Y%m%dt%H%M%S%z | tr '[:upper:]' '[:lower:]')"
container="ness-zabbix-restore-${run_id}"
volume="ness_zabbix_restore_${run_id}"
root_password="$(openssl rand -hex 32)"

cleanup() {
  docker rm -f "${container}" >/dev/null 2>&1 || true
  docker volume rm "${volume}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker volume create "${volume}" >/dev/null
docker run -d --name "${container}" \
  --network none \
  --memory 6g --memory-swap 6g --cpus 4 \
  -e MARIADB_ROOT_PASSWORD="${root_password}" \
  -v "${volume}:/var/lib/mysql" \
  "${mariadb_image}" \
  --innodb-buffer-pool-size=2G \
  --max-allowed-packet=1G >/dev/null

for _ in $(seq 1 90); do
  if docker exec -e CHECK_PASSWORD="${root_password}" "${container}" sh -lc \
    'mariadb-admin ping -uroot -p"$CHECK_PASSWORD" --silent' >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
docker exec -e CHECK_PASSWORD="${root_password}" "${container}" sh -lc \
  'mariadb-admin ping -uroot -p"$CHECK_PASSWORD" --silent' >/dev/null

gzip -dc "${resolved_input}" \
  | docker exec -i -e RESTORE_PASSWORD="${root_password}" "${container}" sh -lc \
      'mariadb -uroot -p"$RESTORE_PASSWORD" --max-allowed-packet=1G'

query() {
  docker exec -i -e RESTORE_PASSWORD="${root_password}" "${container}" sh -lc \
    'mariadb -uroot -p"$RESTORE_PASSWORD" --batch --skip-column-names zabbix' \
    <<<"${1}"
}

tables="$(query 'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE();')"
hosts="$(query 'SELECT COUNT(*) FROM hosts;')"
items="$(query 'SELECT COUNT(*) FROM items;')"
triggers="$(query 'SELECT COUNT(*) FROM triggers;')"
dbversion="$(query 'SELECT mandatory FROM dbversion LIMIT 1;')"

[[ "${tables}" =~ ^[0-9]+$ && "${tables}" -gt 100 ]]
[[ "${hosts}" =~ ^[0-9]+$ && "${hosts}" -gt 0 ]]
[[ "${items}" =~ ^[0-9]+$ && "${items}" -gt 0 ]]
[[ "${triggers}" =~ ^[0-9]+$ && "${triggers}" -gt 0 ]]
[[ "${dbversion}" =~ ^[0-9]+$ ]]

printf 'zabbix_tables=%s\n' "${tables}"
printf 'zabbix_hosts=%s\n' "${hosts}"
printf 'zabbix_items=%s\n' "${items}"
printf 'zabbix_triggers=%s\n' "${triggers}"
printf 'zabbix_dbversion=%s\n' "${dbversion}"
printf 'isolated_restore=PASS\n'
