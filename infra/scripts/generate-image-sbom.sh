#!/usr/bin/env bash
# Inventory the exact locally built images; never scan a moving remote tag.
set -euo pipefail
umask 077
output="${1:?output directory required}"
shift
(( $# > 0 )) || { echo 'at least one local image is required' >&2; exit 2; }
mkdir -p "$output"
if [[ -n "$(find "$output" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo 'output directory must be empty to avoid mixing SBOM runs' >&2
  exit 2
fi
manifest="$output/images.tsv"
: > "$manifest"
for image in "$@"; do
  identity=$(docker image inspect --format '{{.Id}}' "$image")
  [[ "$identity" =~ ^sha256:[0-9a-f]{64}$ ]]
  filename="${identity#sha256:}.cdx.json"
  syft "docker:$identity" -o "cyclonedx-json=$output/$filename"
  printf '%s\t%s\t%s\n' "$image" "$identity" "$filename" >> "$manifest"
done
python3 - "$output" <<'PY'
import json, pathlib, sys
root=pathlib.Path(sys.argv[1])
records=[]
for line in (root/'images.tsv').read_text().splitlines():
    reference,identity,filename=line.split('\t')
    bom=json.loads((root/filename).read_text())
    assert bom.get('bomFormat')=='CycloneDX'
    count=len(bom.get('components',[]))
    assert count>0, f'empty SBOM for {reference}'
    records.append(dict(reference=reference,image_id=identity,sbom=filename,components=count))
(root/'index.json').write_text(json.dumps({'images':records},indent=2)+'\n')
print(json.dumps({'sbom_images':len(records),'components':[r['components'] for r in records]}))
PY
(cd "$output" && sha256sum *.cdx.json index.json > SHA256SUMS)
