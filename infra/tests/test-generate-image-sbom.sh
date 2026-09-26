#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
temp_root="$(mktemp -d)"
trap 'rm -rf -- "$temp_root"' EXIT
mkdir -p "$temp_root/bin"

cat >"$temp_root/bin/docker" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
[[ "$1" == image && "$2" == inspect && "$3" == --format ]]
case "$5" in
  backend:ci) printf 'sha256:%064d\n' 1 ;;
  frontend:ci) printf 'sha256:%064d\n' 2 ;;
  *) exit 2 ;;
esac
MOCK

cat >"$temp_root/bin/syft" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
[[ "$1" == docker:sha256:* && "$2" == -o && "$3" == cyclonedx-json=* ]]
printf '{"bomFormat":"CycloneDX","components":[{"name":"synthetic"}]}\n' \
  >"${3#cyclonedx-json=}"
MOCK
chmod +x "$temp_root/bin/docker" "$temp_root/bin/syft"

mkdir -p "$temp_root/stale"
printf 'old SBOM\n' >"$temp_root/stale/old.cdx.json"
if PATH="$temp_root/bin:$PATH" bash "$repo_root/infra/scripts/generate-image-sbom.sh" \
  "$temp_root/stale" backend:ci; then
  echo 'generator accepted a non-empty output directory' >&2
  exit 1
fi

PATH="$temp_root/bin:$PATH" bash "$repo_root/infra/scripts/generate-image-sbom.sh" \
  "$temp_root/fresh" backend:ci frontend:ci
(cd "$temp_root/fresh" && sha256sum --check SHA256SUMS >/dev/null)
python3 - "$temp_root/fresh/index.json" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
assert [record["reference"] for record in manifest["images"]] == [
    "backend:ci",
    "frontend:ci",
]
assert all(record["components"] == 1 for record in manifest["images"])
PY
echo 'image SBOM generator checks: PASS'
