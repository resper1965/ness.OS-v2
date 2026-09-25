#!/usr/bin/env bash
# Capture deployment material separately from database/volume consistency.
set -euo pipefail
umask 077
destination="$(realpath -e "${1:?existing backup directory required}")"
case "${destination}" in
  /opt/n-infraops/backups/nightly/*|/opt/n-infraops/backups/deployment/*) ;;
  *) echo 'destination must be within the AIOps backup roots' >&2; exit 2 ;;
esac
[[ ! -e "${destination}/deployment-app.tar.gz" ]] || exit 3
app_dir=/opt/n-infraops/app
compose=(docker compose -f "${app_dir}/docker-compose.yml" -f "${app_dir}/docker-compose.tickets.yml")

# Required build inputs and every active application bind mount. Fail if missing.
tar --exclude='node_modules' --exclude='__pycache__' --exclude='.pytest_cache' \
  --exclude='.git' --exclude='*.tar.gz' \
  -czf "${destination}/deployment-app.tar.gz" -C "${app_dir}" \
  .env Caddyfile Dockerfile docker-compose.yml docker-compose.tickets.yml \
  backend frontend public cli

runtime=(etc/ness-os)
for path in /etc/netplan/60-ness-zabbix-route.yaml \
  /etc/systemd/system/ness-*.service /etc/systemd/system/ness-*.timer \
  /usr/local/sbin/ness-*; do
  [[ ! -e "${path}" ]] || runtime+=("${path#/}")
done
tar -czf "${destination}/deployment-runtime.tar.gz" -C / "${runtime[@]}"

# Do not store docker inspect wholesale: Config.Env contains credentials.
python3 - "${destination}" <<'PY'
import json
import pathlib
import subprocess
import sys

out = pathlib.Path(sys.argv[1])
ids = subprocess.check_output(["docker", "ps", "-aq", "--filter", "name=^/ninf-"], text=True).split()
if not ids:
    raise SystemExit("no AIOps containers found")
containers = json.loads(subprocess.check_output(["docker", "inspect", *ids]))
records = []
for container in containers:
    image = json.loads(subprocess.check_output(["docker", "image", "inspect", container["Image"]]))[0]
    records.append({
        "name": container["Name"].lstrip("/"),
        "image_id": container["Image"],
        "image_reference": container["Config"]["Image"],
        "repo_digests": image.get("RepoDigests", []),
        "mounts": [{key: mount.get(key) for key in ("Type", "Name", "Source", "Destination", "RW")}
                   for mount in container["Mounts"]],
    })
(out / "deployment-images.json").write_text(json.dumps(records, indent=2) + "\n")
print(f"deployment_images_recorded={len(records)}")
# Locally built Compose images have RepoDigests too; those digests do not
# establish that a registry can supply the image after losing this server.
recovery_names = {'ninf-api', 'ninf-frontend', 'ninf-worker-alerts', 'ninf-worker-ml',
                  'ninf-postgres', 'ninf-redis'}
recovery_records = [r for r in records if r['name'] in recovery_names]
if {r['name'] for r in recovery_records} != recovery_names:
    raise SystemExit('required hub recovery container missing')
local_ids = sorted({r['image_id'] for r in recovery_records})
with (out / "deployment-local-images.tar.gz").open("wb") as stream:
    save = subprocess.Popen(["docker", "image", "save", *local_ids], stdout=subprocess.PIPE)
    try:
        subprocess.run(["gzip", "-1"], stdin=save.stdout, stdout=stream, check=True)
    finally:
        save.stdout.close()
    if save.wait() != 0:
        raise SystemExit("Docker image export failed")
print(f"deployment_recovery_images_exported={len(local_ids)}")
PY

gzip -t "${destination}/deployment-local-images.tar.gz"
tar -tzf "${destination}/deployment-local-images.tar.gz" >/dev/null

# The nightly producer already made these dumps. Standalone deployment capture
# must include a fresh hub database too, so restore never needs production.
install -d -m 700 "${destination}/hub-database"
if [[ -f "${destination}/postgres/globals.sql.gz" && -f "${destination}/postgres/nessops.dump" ]]; then
  gzip -dc "${destination}/postgres/globals.sql.gz" > "${destination}/hub-database/globals.sql"
  cp "${destination}/postgres/nessops.dump" "${destination}/hub-database/nessops.dump"
else
  "${compose[@]}" exec -T postgres sh -lc 'pg_dumpall --globals-only -U "$POSTGRES_USER"' \
    > "${destination}/hub-database/globals.sql"
  "${compose[@]}" exec -T postgres sh -lc 'pg_dump -Fc -U "$POSTGRES_USER" nessops' \
    > "${destination}/hub-database/nessops.dump"
fi
"${compose[@]}" exec -T postgres pg_restore -l < "${destination}/hub-database/nessops.dump" >/dev/null
tar -czf "${destination}/deployment-hub-database.tar.gz" -C "${destination}/hub-database" globals.sql nessops.dump
tar -tzf "${destination}/deployment-hub-database.tar.gz" >/dev/null
rm -- "${destination}/hub-database/globals.sql" "${destination}/hub-database/nessops.dump"
rmdir "${destination}/hub-database"
echo 'deployment_hub_database_captured=PASS'

# Compare restored bytes/metadata against the captured sources without writing
# anything into production. A concurrent deployment makes this check fail.
gzip -dc "${destination}/deployment-app.tar.gz" | tar -df - -C "${app_dir}"
gzip -dc "${destination}/deployment-runtime.tar.gz" | tar -df - -C /
echo 'deployment_archives_source_comparison=PASS'
