#!/usr/bin/env bash
# Usage: terraform show -json plan | tf-plan-guard.sh -   (or a plan.json path; never keep it in the repo: it holds secrets)
# Exit 1 if the input is not a plan or any resource is deleted, replaced or forgotten.
set -euo pipefail
python3 -c "$(cat <<'PY'
import json, sys

try:
    plan = json.load(sys.stdin if sys.argv[-1] == "-" else open(sys.argv[-1]))
    if "format_version" not in plan:
        raise ValueError("not a terraform plan")
    bad = [r["address"] for r in plan.get("resource_changes") or []
           if {"delete", "forget"} & set(r["change"]["actions"])]
except (OSError, ValueError, KeyError, TypeError) as e:
    sys.exit(f"plan-guard: unreadable plan: {e}")
if bad:
    sys.exit("plan-guard: delete/replace/forget blocked: " + ", ".join(bad))
PY
)" "${1:?usage: tf-plan-guard.sh <plan.json|->}"
