#!/usr/bin/env bash
# Disposable Docker engine: no production socket, volumes, ports or bridges.
set -Eeuo pipefail
umask 077
snapshot="${1:?exact deployment restic snapshot ID required}"
[[ "$snapshot" =~ ^[0-9a-f]{64}$ ]] || exit 2
exec 7>/run/lock/ness-hub-clean-restore.lock
flock -n 7 || exit 3
work=$(mktemp -d /opt/n-infraops/restore-tests/clean-engine-XXXXXXXX)
engine_pid=''
clean_docker() { docker --host "unix://$work/docker.sock" "$@"; }
cleanup() {
  if [[ -n "$engine_pid" ]]; then
    clean_docker ps -aq | xargs -r docker --host "unix://$work/docker.sock" rm -f >/dev/null 2>&1 || true
    kill "$engine_pid" 2>/dev/null || true
    wait "$engine_pid" 2>/dev/null || true
  fi
  # Do not remove a tree still used by the private daemon/containerd.
  if ! mountpoint -q "$work/data" && ! pgrep -f "containerd.*$work" >/dev/null; then
    rm -rf -- "$work"
  else
    echo "cleanup_requires_review=$work" >&2
  fi
}
trap cleanup EXIT
trap 'echo "clean engine restore failed; diagnostic directory: $work" >&2; tail -30 "$work/daemon.log" >&2' ERR

# Download the exact remotely verified deployment archive.
(
  exec 8>/run/lock/ness-object-storage-restic.lock
  flock -n 8
  set -a
  . /etc/ness-os/backup-s3.env
  set +a
  export RESTIC_REPOSITORY="s3:${CONTABO_S3_ENDPOINT%/}/${CONTABO_S3_BUCKET}/ness-os/${NESS_BACKUP_HOST_ID}/aiops"
  export RESTIC_CACHE_DIR=/var/cache/ness-os-restic
  restic restore "$snapshot" --target "$work/download" --verify
)
mapfile -t manifests < <(find "$work/download" -type f -name SHA256SUMS)
[[ ${#manifests[@]} -eq 1 ]]
deployment=$(dirname "${manifests[0]}")
(cd "$deployment" && sha256sum -c SHA256SUMS)
mkdir "$work/app"
tar -xzf "$deployment/deployment-app.tar.gz" -C "$work/app"

# All application/database/image material must come from this remote snapshot.
# No fallback to the production Docker socket or database is permitted.
test -f "$deployment/deployment-hub-database.tar.gz"
tar -xzf "$deployment/deployment-hub-database.tar.gz" -C "$work" globals.sql nessops.dump
echo 'restore_source=remote_snapshot_only'

printf '{}\n' > "$work/daemon.json"
dockerd --config-file "$work/daemon.json" --host "unix://$work/docker.sock" \
  --pidfile "$work/docker.pid" --data-root "$work/data" --exec-root "$work/run" \
  --containerd-namespace "$(basename "$work")" \
  --containerd-plugins-namespace "plugins-$(basename "$work")" \
  --bridge none --iptables=false --ip6tables=false --ip-forward=false --ip-masq=false \
  --storage-driver vfs > "$work/daemon.log" 2>&1 &
engine_pid=$!
for _ in $(seq 1 60); do
  if clean_docker info >/dev/null 2>&1; then break; fi
  kill -0 "$engine_pid"
  sleep 1
done
clean_docker info >/dev/null
[[ -z "$(clean_docker image ls -q)" ]]
[[ "$(clean_docker info --format '{{.DockerRootDir}}')" == "$work/data" ]]
echo 'clean_engine_initial_images=0'
clean_docker image load -i "$deployment/deployment-local-images.tar.gz"
python3 - "$deployment/deployment-images.json" "$work/images.env" \
  "$deployment/deployment-local-images.tar.gz" <<'PY'
import hashlib,json,sys,tarfile
names={'ninf-api':'API_IMAGE','ninf-frontend':'FRONTEND_IMAGE',
       'ninf-worker-alerts':'ALERTS_IMAGE','ninf-worker-ml':'ML_IMAGE',
       'ninf-postgres':'PG_IMAGE_RUNTIME','ninf-redis':'REDIS_IMAGE_RUNTIME'}
rows=json.load(open(sys.argv[1]))
selected={names[r['name']]:r['image_id'] for r in rows if r['name'] in names}
assert len(selected)==6
# The production containerd store identifies an OCI index; the clean vfs
# store identifies its platform image config. Resolve from verified archive
# metadata rather than guessing tags or requiring identical store formats.
metadata={}
for path in sys.argv[3:]:
    with tarfile.open(path,'r|*') as archive:
        for member in archive:
            if not member.isfile() or not member.name.startswith('blobs/sha256/') or member.size>65536:
                continue
            raw=archive.extractfile(member).read()
            try:
                value=json.loads(raw)
            except (ValueError,UnicodeError):
                continue
            digest=hashlib.sha256(raw).hexdigest()
            assert digest==member.name.split('/')[-1]
            metadata['sha256:'+digest]=value
def runtime_id(digest):
    value=metadata[digest]
    if 'manifests' in value:
        matches=[m for m in value['manifests'] if m.get('platform',{}).get('os')=='linux'
                 and m.get('platform',{}).get('architecture')=='amd64']
        assert len(matches)==1
        return runtime_id(matches[0]['digest'])
    if 'config' in value and isinstance(value['config'],dict) and 'digest' in value['config']:
        return value['config']['digest']
    assert 'rootfs' in value
    return digest
open(sys.argv[2],'w').write(''.join(f'{k}={runtime_id(v)}\n' for k,v in selected.items()))
print('image_platform_config_identities_verified='+str(len(selected)))
PY
. "$work/images.env"
for id in "$API_IMAGE" "$FRONTEND_IMAGE" "$ALERTS_IMAGE" "$ML_IMAGE"; do
  clean_docker image inspect "$id" >/dev/null
done
clean_docker run -d --name restore-pg --network none --memory 1g --cpus 1 \
  -e POSTGRES_USER=restore_admin -e POSTGRES_PASSWORD=restore-test-only \
  -e POSTGRES_DB=restore_control "$PG_IMAGE_RUNTIME" >/dev/null
for _ in $(seq 1 90); do
  if clean_docker logs restore-pg 2>&1 | grep 'PostgreSQL init process complete' >/dev/null \
    && clean_docker exec restore-pg pg_isready -U restore_admin >/dev/null 2>&1; then break; fi
  sleep 1
done
clean_docker exec -i restore-pg psql -X -v ON_ERROR_STOP=1 -U restore_admin -d restore_control < "$work/globals.sql" >/dev/null
clean_docker exec -i restore-pg pg_restore --exit-on-error --create -U restore_admin -d restore_control < "$work/nessops.dump"
clean_docker exec restore-pg psql -X -v ON_ERROR_STOP=1 -U restore_admin -d restore_control \
  -c "ALTER ROLE nessops PASSWORD 'restore-test-only'" >/dev/null
clean_docker run -d --name restore-redis --network container:restore-pg --memory 256m "$REDIS_IMAGE_RUNTIME" >/dev/null
common=(--network container:restore-pg --memory 768m --cpus 1
  -v "$work/app/backend/app:/app/app:ro"
  -e NINF_DATABASE_URL=postgresql+asyncpg://nessops:restore-test-only@127.0.0.1:5432/nessops
  -e NINF_REDIS_URL=redis://127.0.0.1:6379/0
  -e NINF_CELERY_BROKER_URL=redis://127.0.0.1:6379/1
  -e NINF_CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2
  -e NINF_ALERT_NOTIFICATIONS_ENABLED=false -e NINF_TRANSACTIONAL_EMAIL_ENABLED=false
  -e NINF_JWT_SECRET=isolated-restore-no-production-access)
clean_docker run -d --name restore-api "${common[@]}" "$API_IMAGE" \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 >/dev/null
clean_docker run -d --name restore-frontend --network container:restore-pg \
  --memory 512m --cpus 1 "$FRONTEND_IMAGE" >/dev/null
clean_docker run -d --name restore-alerts "${common[@]}" "$ALERTS_IMAGE" \
  celery -A app.workers.celery_app worker --concurrency=1 -Q alerts.primary,alerts.deferred -n restore-alerts@restore >/dev/null
clean_docker run -d --name restore-ml "${common[@]}" "$ML_IMAGE" \
  celery -A app.workers.celery_app worker --concurrency=1 -Q ml -n restore-ml@restore >/dev/null
for _ in $(seq 1 60); do
  if clean_docker exec restore-api curl -fsS http://127.0.0.1:8000/ > "$work/api.json" \
    && clean_docker exec restore-api curl -fsS http://127.0.0.1:3000/ > "$work/frontend.html"; then break; fi
  sleep 1
done
python3 - "$work" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1])
assert json.loads((p/'api.json').read_text())['platform']=='ness.OS'
assert '<div id="root">' in (p/'frontend.html').read_text()
print('restored_api_and_frontend_http=PASS')
PY
clean_docker exec -i restore-api python - <<'PY'
import asyncio,socket
from sqlalchemy import text
from app.database import engine
assert {name for _,name in socket.if_nameindex()} == {'lo'}
print('restored_api_network_interfaces=loopback_only')
async def check():
    async with engine.connect() as conn:
        for table in ('incidents','assets','users'):
            result=await conn.execute(text('SELECT count(*) FROM n_infraops_'+table))
            count=result.scalar_one()
            assert count>0, table
            print(f'restored_backend_database_{table}={count}')
    await engine.dispose()
asyncio.run(check())
PY
clean_docker exec restore-api celery -A app.workers.celery_app inspect ping --timeout 10 > "$work/workers.txt"
grep 'restore-alerts@restore' "$work/workers.txt" >/dev/null
grep 'restore-ml@restore' "$work/workers.txt" >/dev/null
echo 'restored_workers_ping=2'
echo "hub_clean_engine_restore=PASS deployment_snapshot=$snapshot"
