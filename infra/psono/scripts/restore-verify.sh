#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly s3_env="${PSONO_S3_ENV:-/etc/ness-os/backup-s3.env}"
readonly target="${PSONO_RESTORE_VERIFY_ROOT:-/var/lib/ness-os/psono-restore-verify}"
readonly started_at="$(date +%s)"
readonly run_id="$(date +%Y%m%d%H%M%S)-$$"
readonly container="ness-psono-restore-${run_id}"
readonly app_container="ness-psono-app-restore-${run_id}"
readonly volume="ness_psono_restore_${run_id}"
exec 9>/run/lock/ness-psono-restore-verify.lock
flock -n 9 || { echo 'another restore verification is running' >&2; exit 5; }

[[ ${target} == /var/lib/ness-os/psono-restore-verify ]] || {
  echo 'unexpected restore verification target' >&2
  exit 2
}
[[ -f ${s3_env} && ! -L ${s3_env} ]] || { echo 'backup environment is unavailable' >&2; exit 3; }

set -a
# shellcheck disable=SC1090
. "${s3_env}"
set +a
export RESTIC_REPOSITORY="s3:${CONTABO_S3_ENDPOINT%/}/${CONTABO_S3_BUCKET}/ness-os/psono-prod/psono"
export RESTIC_CACHE_DIR=/var/cache/ness-os-restic

rm -rf -- "${target}"
install -d -m 0700 -o root -g root "${target}"
cleanup() {
  docker rm -f "${app_container}" >/dev/null 2>&1 || true
  docker rm -f "${container}" >/dev/null 2>&1 || true
  docker volume rm "${volume}" >/dev/null 2>&1 || true
  rm -rf -- "${target}"
}
trap cleanup EXIT
restic restore latest --target "${target}"

set_dir="$(find "${target}" -type f -name COMPLETED -printf '%h\n' | head -n1)"
[[ -n ${set_dir} && -f ${set_dir}/SHA256SUMS ]] || { echo 'completed backup set not found' >&2; exit 4; }
(
  cd "${set_dir}"
  sha256sum --check SHA256SUMS
  docker exec -i ness-psono-db pg_restore --list <psono.pgdump >/dev/null
  tar --list --gzip --file configuration.tar.gz >/dev/null
)

# Import into a disposable database with the same image as production. No
# production volume, published port or network is attached to this container.
image="$(docker inspect --format '{{.Image}}' ness-psono-db)"
docker volume create "${volume}" >/dev/null
docker run -d --name "${container}" --network none --memory 512m --cpus 1 \
  -e POSTGRES_USER=psono -e POSTGRES_DB=psono \
  -e POSTGRES_PASSWORD=restore-test-only \
  -v "${volume}:/var/lib/postgresql/data" "${image}" >/dev/null
for _ in $(seq 1 120); do
  if docker logs "${container}" 2>&1 | grep 'PostgreSQL init process complete' >/dev/null \
    && docker exec "${container}" pg_isready -U psono -d psono >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker logs "${container}" 2>&1 | grep 'PostgreSQL init process complete' >/dev/null
docker exec "${container}" pg_isready -U psono -d psono >/dev/null
docker exec -i "${container}" pg_restore --exit-on-error -U psono -d psono \
  <"${set_dir}/psono.pgdump"
docker exec -i "${container}" psql -X -At -v ON_ERROR_STOP=1 -U psono -d psono <<'SQL'
SELECT format('SELECT %L, count(*) FROM %I.%I;', tablename, schemaname, tablename)
FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename
\gexec
SQL
table_count="$(docker exec "${container}" psql -X -At -U psono -d psono \
  -c "SELECT count(*) FROM pg_tables WHERE schemaname='public'")"
[[ "${table_count}" -gt 0 ]] || { echo 'restored database is empty' >&2; exit 6; }
echo "psono_tables_restored=${table_count}"

# Boot the actual application with the backed-up keys. It shares only the
# disposable DB's network namespace (network=none), with no external routes.
app_image="$(docker inspect --format '{{.Image}}' ness-psono)"
install -d -m 700 "${target}/app-config"
tar -xzf "${set_dir}/configuration.tar.gz" -C "${target}/app-config" \
  runtime/settings.yaml runtime/config.json
docker run --rm -i --network none --entrypoint python3 \
  -v "${target}/app-config/runtime:/restore" "${app_image}" - <<'PY'
from pathlib import Path
import yaml
p = Path('/restore/settings.yaml')
s = yaml.safe_load(p.read_text())
for key in ('SECRET_KEY', 'ACTIVATION_LINK_SECRET', 'DB_SECRET', 'PRIVATE_KEY', 'PUBLIC_KEY'):
    assert s.get(key), f'Missing backed-up key: {key}'
s['DATABASES']['default'].update(HOST='127.0.0.1', PORT='5432', NAME='psono', USER='psono', PASSWORD='restore-test-only')
s['ALLOWED_HOSTS'] = ['restore.invalid', 'localhost', '127.0.0.1']
p.write_text(yaml.safe_dump(s))
PY
docker run -d --name "${app_container}" --network "container:${container}" \
  --memory 1g --cpus 1 -e PSONO_DOMAIN=restore.invalid \
  -v "${target}/app-config/runtime/settings.yaml:/root/.psono_server/settings.yaml:ro" \
  -v "${target}/app-config/runtime/config.json:/usr/share/nginx/html/config.json:ro" \
  "${app_image}" >/dev/null
for _ in $(seq 1 120); do
  if docker exec "${app_container}" curl -fsS -H 'Host: restore.invalid' \
    http://127.0.0.1/server/info/ >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec -i "${app_container}" python3 - <<'PY'
import json
import requests
import yaml
from nacl.signing import VerifyKey
from nacl.encoding import HexEncoder
s = yaml.safe_load(open('/root/.psono_server/settings.yaml'))
r = requests.get('http://127.0.0.1/server/info/', headers={'Host': 'restore.invalid'}, timeout=10)
r.raise_for_status()
body = r.json()
VerifyKey(body['verify_key'], encoder=HexEncoder).verify(body['info'].encode(), bytes.fromhex(body['signature']))
assert json.loads(body['info'])['public_key'] == s['PUBLIC_KEY']
print('psono_restored_application_http=200')
print('psono_restored_info_signature=valid')
print('psono_restored_public_key=matches_backup')
PY
echo "psono_restore_elapsed_seconds=$(( $(date +%s) - started_at ))"
echo "psono_restore_backup_set=$(basename "${set_dir}")"
echo 'psono_restore_verify=PASS'
