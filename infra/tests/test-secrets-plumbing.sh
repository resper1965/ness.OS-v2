#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
renderer="${repo_root}/infra/secrets/render-env.sh"
installer="${repo_root}/infra/secrets/install-sops-age.sh"
compose_file="${repo_root}/app/docker-compose.yml"
env_example="${repo_root}/app/.env.example"

[[ -s ${repo_root}/.sops.yaml.example ]]
[[ -s ${renderer} ]]
[[ -s ${installer} ]]
grep -q 'CUSTODIAN_1' "${repo_root}/.sops.yaml.example"
grep -q 'CUSTODIAN_2' "${repo_root}/.sops.yaml.example"
grep -q 'destination must be an explicit ness-os env path' "${renderer}"
grep -q 'sops --decrypt --output-type dotenv' "${renderer}"
grep -q "readonly sops_version='3.13.3'" "${installer}"
grep -q "readonly age_version='1.3.2'" "${installer}"
grep -q 'refusing to overwrite' "${installer}"
grep -q 'sha256sum --check --status' "${installer}"
grep -q '/etc/ness-os/glpi-integration.env' "${compose_file}"
grep -q '/etc/ness-os/zabbix-integration.env' "${compose_file}"
[[ $(grep -c '/etc/ness-os/glpi-integration.env' "${compose_file}") -eq 2 ]]
[[ $(grep -c '/etc/ness-os/zabbix-integration.env' "${compose_file}") -eq 2 ]]
grep -q '^NINF_GLPI_URL=http://ninf-glpi/apirest.php$' "${env_example}"
bash -n "${renderer}"
bash -n "${installer}"
echo 'secrets plumbing static checks: PASS'
