#!/usr/bin/env bash
set -euo pipefail
report_dir=/var/lib/ness-os/hub-integration
install -d -m 700 "$report_dir"
status=0
exec 9>"$report_dir/monitor.lock"
flock -n 9 || exit 0
temporary=$(mktemp "$report_dir/.probe-XXXXXX")
trap 'rm -f -- "$temporary"' EXIT
# Leave time for publishing a failure sample before systemd's 55-second deadline.
timeout --kill-after=2s 40s docker exec ninf-api timeout --kill-after=2s 35s python -m app.integrations.pipeline_health > "$temporary" || status=$?
python3 /usr/local/sbin/ness-hub-health-history --directory "$report_dir" --exit-code "$status" < "$temporary"
