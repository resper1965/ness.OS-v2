#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
renderer="${repo_root}/infra/secrets/render-env.sh"

[[ -s ${repo_root}/.sops.yaml.example ]]
[[ -s ${renderer} ]]
grep -q 'CUSTODIAN_1' "${repo_root}/.sops.yaml.example"
grep -q 'CUSTODIAN_2' "${repo_root}/.sops.yaml.example"
grep -q 'destination must be an explicit ness-os env path' "${renderer}"
grep -q 'sops --decrypt --output-type dotenv' "${renderer}"
bash -n "${renderer}"
echo 'secrets plumbing static checks: PASS'
