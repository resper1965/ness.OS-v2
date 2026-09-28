#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

render_identity_metadata() {
  local inventory="$1"
  python3 - "${repo_root}" "${inventory}" <<'PY'
import csv
import json
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
inventory = Path(sys.argv[2])
fields = ("identity", "consumer", "source", "scope", "rotated_at", "expires_at")
rows = []
with inventory.open(encoding="utf-8", newline="") as source:
    for line_number, row in enumerate(csv.reader(source, delimiter="\t"), start=1):
        if not row or (len(row) == 1 and not row[0]):
            continue
        if len(row) != len(fields):
            raise SystemExit(f"invalid identity inventory row {line_number}: expected 6 tab-separated fields")
        record = dict(zip(fields, row, strict=True))
        if not record["identity"] or not record["consumer"] or not record["source"]:
            raise SystemExit(f"invalid identity inventory row {line_number}: identity, consumer and source are required")
        if "://" in record["source"]:
            raise SystemExit(f"invalid source on identity inventory row {line_number}; use a protected file path")
        for field in ("rotated_at", "expires_at"):
            if record[field]:
                try:
                    date.fromisoformat(record[field])
                except ValueError:
                    raise SystemExit(f"invalid {field} on identity inventory row {line_number}; expected YYYY-MM-DD")
        if record["rotated_at"] and date.fromisoformat(record["rotated_at"]) > datetime.now(timezone.utc).date():
            raise SystemExit(f"invalid rotated_at on identity inventory row {line_number}; date cannot be in the future")
        rows.append(record)

def source_path(record):
    path = Path(record["source"])
    return path if path.is_absolute() else repo / path

source_counts = Counter(source_path(record).resolve() for record in rows)
today = datetime.now(timezone.utc).date()
for record in rows:
    resolved = source_path(record).resolve()
    tracked = False
    try:
        relative = resolved.resolve().relative_to(repo)
        tracked = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--error-unmatch", str(relative)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
    except ValueError:
        pass

    statuses = []
    if not resolved.is_file():
        statuses.append("missing")
    if source_counts[resolved] > 1:
        statuses.append("shared")
    if tracked:
        statuses.append("versioned")
    if record["expires_at"] and date.fromisoformat(record["expires_at"]) <= today:
        statuses.append("expired")
    elif not record["expires_at"]:
        statuses.append("expiry_unverified")
    if not record["scope"]:
        statuses.append("scope_unverified")
    if not record["rotated_at"]:
        statuses.append("rotation_unverified")
    age = (today - date.fromisoformat(record["rotated_at"])).days if record["rotated_at"] else None
    print(json.dumps({
        "identity": record["identity"],
        "consumer": record["consumer"],
        "source": record["source"],
        "scope": record["scope"] or "unverified",
        "rotation_age_days": age,
        "expires_at": record["expires_at"] or None,
        "status": statuses or ["ok"],
    }, sort_keys=True))
PY
}

case "${1:-}" in
  --metadata-only)
    [[ $# -eq 2 && -f "$2" ]] || { echo 'usage: aiops-secret-consumer-report.sh --metadata-only INVENTORY.tsv' >&2; exit 2; }
    render_identity_metadata "$2"
    exit
    ;;
  --metadata-file)
    [[ $# -eq 2 && -f "$2" ]] || { echo 'usage: aiops-secret-consumer-report.sh --metadata-file INVENTORY.tsv' >&2; exit 2; }
    metadata_file="$2"
    ;;
  '')
    metadata_file=''
    ;;
  *)
    echo 'usage: aiops-secret-consumer-report.sh [--metadata-file INVENTORY.tsv]' >&2
    exit 2
    ;;
esac

redact_uri() {
  sed -E 's#(://[^:]+):[^@]+@#\1:[REDACTED]@#'
}

printf 'api_db='
docker exec ninf-api sh -lc 'printf "%s\n" "$NINF_DATABASE_URL"' | redact_uri
printf 'evolution_db='
docker exec ninf-evolution sh -lc 'printf "%s\n" "$DATABASE_CONNECTION_URI"' | redact_uri
printf 'authentik_db_user='
docker exec ninf-authentik-server sh -lc 'printf "%s\n" "$AUTHENTIK_POSTGRESQL__USER"'
printf 'authentik_db_name='
docker exec ninf-authentik-server sh -lc 'printf "%s\n" "$AUTHENTIK_POSTGRESQL__NAME"'
printf 'authentik_secret_present='
docker exec ninf-authentik-server sh -lc 'test -n "$AUTHENTIK_SECRET_KEY" && echo yes || echo no'
printf 'postgres_compose_password_present='
docker exec ninf-postgres sh -lc 'test -n "$POSTGRES_PASSWORD" && echo yes || echo no'

api_password="$(docker exec ninf-api sh -lc 'printf "%s" "$NINF_DATABASE_URL"' | sed -E 's#^[^:]+://[^:]+:([^@]+)@.*#\1#')"
evolution_password="$(docker exec ninf-evolution sh -lc 'printf "%s" "$DATABASE_CONNECTION_URI"' | sed -E 's#^[^:]+://[^:]+:([^@]+)@.*#\1#')"
authentik_password="$(docker exec ninf-authentik-server sh -lc 'printf "%s" "$AUTHENTIK_POSTGRESQL__PASSWORD"')"
postgres_password="$(docker exec ninf-postgres sh -lc 'printf "%s" "$POSTGRES_PASSWORD"')"
authentik_secret="$(docker exec ninf-authentik-server sh -lc 'printf "%s" "$AUTHENTIK_SECRET_KEY"')"

printf 'shared_database_password_consistent='
if [[ -n "${api_password}" && "${api_password}" == "${evolution_password}" \
  && "${api_password}" == "${authentik_password}" \
  && "${api_password}" == "${postgres_password}" ]]; then
  echo yes
else
  echo no
fi
printf 'database_password_uses_known_default='
[[ "${api_password}" == changeme ]] && echo yes || echo no
printf 'authentik_secret_uses_compose_default='
[[ "${authentik_secret}" == 'f1e5CICu!vyh_supersecret' ]] && echo yes || echo no

unset api_password evolution_password authentik_password postgres_password authentik_secret

if [[ -n "${metadata_file}" ]]; then
  echo 'service_identity_metadata_begin'
  render_identity_metadata "${metadata_file}"
  echo 'service_identity_metadata_end'
else
  echo 'service_identity_metadata=unverified (provide --metadata-file from the protected inventory)'
fi
