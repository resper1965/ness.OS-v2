#!/usr/bin/env bash
# Usage: tf-plan-guard.sh <plan.json>  (from `terraform show -json`). Exit 1 if any resource is deleted or replaced.
set -euo pipefail
python3 - "${1:?usage: tf-plan-guard.sh <plan.json>}" <<'PY'
import json, sys

bad = [r["address"] for r in json.load(open(sys.argv[1])).get("resource_changes", []) if "delete" in r["change"]["actions"]]
if bad:
    sys.exit("plan-guard: delete/replace blocked: " + ", ".join(bad))
PY
