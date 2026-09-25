#!/usr/bin/env bash
set -euo pipefail
report_dir=/var/lib/ness-os/hub-integration
install -d -m 700 "$report_dir"
docker exec ninf-api python -m app.integrations.cmdb_sync --apply > "$report_dir/cmdb.tmp"
chmod 600 "$report_dir/cmdb.tmp"
mv "$report_dir/cmdb.tmp" "$report_dir/cmdb.json"
