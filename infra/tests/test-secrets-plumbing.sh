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

report="${repo_root}/infra/scripts/aiops-secret-consumer-report.sh"
fixture_dir="$(mktemp -d)"
trap 'rm -rf "${fixture_dir}"' EXIT
mkdir -p "${fixture_dir}/bin"
cat >"${fixture_dir}/bin/docker" <<'DOCKER'
#!/usr/bin/env bash
exit 0
DOCKER
chmod +x "${fixture_dir}/bin/docker"
shared_source="${fixture_dir}/shared.env"
printf 'fixture-only=not-a-secret\n' >"${shared_source}"
future_date="$(date -u -d '+30 days' +%F)"
past_date="$(date -u -d 'yesterday' +%F)"
printf 'missing\tmissing-consumer\t%s\tread-only\t2026-01-01\t%s\n' "${fixture_dir}/absent.env" "${future_date}" >"${fixture_dir}/identities.tsv"
printf 'shared-a\tapi\t%s\tread-only\t2026-01-01\t%s\n' "${shared_source}" "${future_date}" >>"${fixture_dir}/identities.tsv"
printf 'shared-b\tworker\t%s\tread-only\t2026-01-01\t%s\n' "${shared_source}" "${future_date}" >>"${fixture_dir}/identities.tsv"
printf 'expired\tzabbix\t%s\tread-only\t2025-01-01\t%s\n' "${shared_source}" "${past_date}" >>"${fixture_dir}/identities.tsv"
printf 'versioned\tfixture\tapp/.env.example\tread-only\t2026-01-01\t%s\n' "${future_date}" >>"${fixture_dir}/identities.tsv"
printf 'no-expiry\tobject-storage\t%s\tread-only\t2026-01-01\t\n' "${fixture_dir}/no-expiry.env" >>"${fixture_dir}/identities.tsv"
printf 'metadata-only\n' >"${fixture_dir}/no-expiry.env"
report_output="$(PATH="${fixture_dir}/bin:${PATH}" bash "${report}" --metadata-only "${fixture_dir}/identities.tsv")"
REPORT_OUTPUT="${report_output}" python3 - <<'PY'
import json
import os

records = [json.loads(line) for line in os.environ["REPORT_OUTPUT"].splitlines()]
by_name = {record["identity"]: record for record in records}
assert by_name["missing"]["status"] == ["missing"]
assert "shared" in by_name["shared-a"]["status"]
assert "shared" in by_name["shared-b"]["status"]
assert "expired" in by_name["expired"]["status"]
assert "versioned" in by_name["versioned"]["status"]
assert "expiry_unverified" in by_name["no-expiry"]["status"]
assert all("secret" not in record for record in records)
assert all("fixture-only=not-a-secret" not in line for line in os.environ["REPORT_OUTPUT"].splitlines())
PY
echo 'secrets plumbing static checks: PASS'
