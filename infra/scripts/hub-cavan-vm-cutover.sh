#!/usr/bin/env bash
# Run on the hub after copying the two reviewed PHP scripts into ninf-glpi:/tmp.
set -euo pipefail
if [[ "${1:-}" != "--apply" ]]; then
    echo 'Refusing cutover without --apply.' >&2
    exit 2
fi
shift
if (($#)); then
    echo 'Usage: hub-cavan-vm-cutover.sh --apply' >&2
    exit 2
fi
umask 077
evidence=/opt/n-infraops/rollback/recovery-20260908
stamp=$(date -u +%Y%m%dT%H%M%SZ)
snapshot="/tmp/cavan-vm-before-$stamp.json"
applied=0
paused=0
timer_was_active=0
exec 9>/run/ness-cavan-vm-cutover.lock
flock -n 9
systemctl is-active --quiet ness-hub-cmdb-sync.timer && timer_was_active=1
for worker in ninf-worker-alerts ninf-worker-ml; do
    test "$(docker inspect -f '{{.State.Running}}' "$worker")" = true
done
recover() {
    status=$?
    trap - EXIT
    if (( status != 0 && applied == 1 )); then
        if ! docker exec -u 0 ninf-glpi php /tmp/glpi-cavan-vm-migrate.php --rollback "$snapshot" > "$evidence/cavan-vm-rollback-$stamp.json"; then
            echo 'Rollback failed; consumers remain paused for reconciliation.' >&2
            exit "$status"
        fi
        if ! docker exec ninf-api python -m app.integrations.cmdb_sync --apply > "$evidence/cavan-vm-rollback-hub-$stamp.json"; then
            echo 'Hub rollback reconciliation failed; consumers remain paused.' >&2
            exit "$status"
        fi
    fi
    if (( paused == 1 )); then docker start ninf-worker-alerts ninf-worker-ml; fi
    if (( timer_was_active == 1 )); then systemctl start ness-hub-cmdb-sync.timer; fi
    exit "$status"
}
trap recover EXIT
systemctl stop ness-hub-cmdb-sync.timer
if systemctl is-active --quiet ness-hub-cmdb-sync.service; then
    echo 'Reconciler currently running; retry after it finishes.' >&2
    exit 1
fi
# Graceful TERM only. Do not force-kill running tasks or discard queue contents.
paused=1
docker kill --signal=TERM ninf-worker-alerts ninf-worker-ml
for attempt in $(seq 1 60); do
    running=$(docker inspect -f '{{.State.Running}}' ninf-worker-alerts ninf-worker-ml)
    if ! grep -q true <<< "$running"; then break; fi
    sleep 1
done
if grep -q true <<< "$(docker inspect -f '{{.State.Running}}' ninf-worker-alerts ninf-worker-ml)"; then
    echo 'Consumers did not drain; migration cancelled.' >&2
    exit 1
fi
docker exec -u 0 ninf-glpi php /tmp/glpi-cavan-vm-migration-audit.php "$snapshot" > "$evidence/cavan-vm-preflight-$stamp.json"
docker cp "ninf-glpi:$snapshot" "$evidence/cavan-vm-before-$stamp.json"
docker exec -u 0 ninf-glpi php /tmp/glpi-cavan-vm-migrate.php --apply "$snapshot" > "$evidence/cavan-vm-applied-$stamp.json"
applied=1
docker exec -u 0 ninf-glpi php /tmp/glpi-cavan-vm-migrate.php --apply "$snapshot" > "$evidence/cavan-vm-replay-$stamp.json"
docker exec ninf-api python -m app.integrations.cmdb_sync --apply > "$evidence/cavan-vm-hub-$stamp.json"
docker exec -i ninf-api python - <<'PY'
import asyncio
import json
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Asset, Incident
from app.integrations.glpi import GLPIClient

async def main():
    glpi = GLPIClient()
    try:
        await glpi.change_active_entity(8)
        computers = await glpi.list_items('Computer')
        network = await glpi.list_items('NetworkEquipment')
        async with SessionLocal() as session:
            for host, asset_id, old_id in [('10882', 190, 120), ('10883', 191, 121), ('10884', 192, 122)]:
                asset = (await session.execute(select(Asset).where(Asset.zabbix_host_id == host))).scalar_one()
                assert asset.id == asset_id and asset.customer_id == 'cavan'
                assert asset.tags['glpi_itemtype'] == 'Computer'
                assert int(asset.tags['glpi_entity_id']) == 8
                target = [c for c in computers if int(c['id']) == int(asset.tags['glpi_item_id'])]
                assert len(target) == 1 and int(target[0]['entities_id']) == 8
                assert f'Zabbix Host ID: {host}' in target[0]['comment']
                assert not any(int(n['id']) == old_id for n in network)
                incidents = (await session.execute(select(Incident.id).where(Incident.asset_id == asset.id))).scalars().all()
                print(json.dumps({'host_id': host, 'asset_id': asset.id, 'computer_id': target[0]['id'], 'incident_ids': incidents}))
    finally:
        await glpi.kill_session()

asyncio.run(main())
PY
cat "$evidence/cavan-vm-applied-$stamp.json" "$evidence/cavan-vm-replay-$stamp.json" "$evidence/cavan-vm-hub-$stamp.json"
echo "Evidence: $evidence/cavan-vm-*-$stamp.json"
