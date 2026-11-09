#!/usr/bin/env bash
# `backup zabbix` ships only the nightly root; `backup zabbix-cutover` ships only the cutover root
# (even when a nightly set is newer), both into the same `zabbix` repository.
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source_script="${repo_root}/infra/scripts/ness-object-storage-restic.sh"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "${tmpdir}"' EXIT

nightly="${tmpdir}/nightly"
cutover="${tmpdir}/cutover"
fake_bin="${tmpdir}/bin"
mkdir -p "${fake_bin}" "${tmpdir}/cache"

make_set() { # root id
  local dir="$1/$2"
  mkdir -p "${dir}"
  printf '{"backup_set_id":"%s"}\n' "$2" >"${dir}/backup-set-manifest.json"
  printf 'dump-%s\n' "$2" >"${dir}/dump"
  (cd "${dir}" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)
  touch "${dir}/COMPLETED"
}
# cutover sets: one OLDER and one NEWER than the nightly; the nightly must never win for cutover
make_set "${nightly}" 20261108T220000-0300
make_set "${cutover}" 20261101T100000-0300
make_set "${cutover}" 20261109T120000-0300

sed \
  -e 's/\[\[ \${EUID} -eq 0 \]\]/true/' \
  -e "s|\"/var/backups/zabbix/nightly\"|\"${nightly}\"|" \
  -e "s|\"/var/backups/zabbix/cutover\"|\"${cutover}\"|" \
  -e 's/install -d -o root -g root/install -d/' \
  -e "s|/run/lock/|${tmpdir}/|g" \
  -e "s|== \"0\" \]\]|== \"\$(id -u)\" ]]|" \
  "${source_script}" >"${tmpdir}/script.sh"

cat >"${tmpdir}/env" <<'ENVF'
CONTABO_S3_ENDPOINT=https://s3.example.test
CONTABO_S3_BUCKET=bucket
AWS_ACCESS_KEY_ID=fixture
AWS_SECRET_ACCESS_KEY=fixture
RESTIC_PASSWORD=fixture
NESS_BACKUP_HOST_ID=zabbix-prod
ENVF
chmod 600 "${tmpdir}/env"

cat >"${fake_bin}/restic" <<'STUB'
#!/usr/bin/env bash
if [[ "$*" == *" backup "* || "$*" == *"--retry-lock 30m backup"* ]]; then
  printf 'repo=%s cwd=%s args=%s\n' "${RESTIC_REPOSITORY}" "$(pwd)" "$*" >>"${RESTIC_STUB_LOG}"
fi
exit 0
STUB
cat >"${fake_bin}/flock" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
chmod +x "${fake_bin}"/*
export PATH="${fake_bin}:${PATH}" RESTIC_STUB_LOG="${tmpdir}/restic.log"
export NESS_RESTIC_ENV_FILE="${tmpdir}/env" RESTIC_CACHE_DIR="${tmpdir}/cache"

run() { : >"${RESTIC_STUB_LOG}"; bash "${tmpdir}/script.sh" backup "$1" 2>&1; }

out="$(run zabbix-cutover)"
grep -Fq 'backup_set_id=20261109T120000-0300' <<<"${out}"
grep -Fq "cwd=${cutover}/20261109T120000-0300" "${RESTIC_STUB_LOG}"
grep -Fq '/ness-os/zabbix-prod/zabbix ' "${RESTIC_STUB_LOG}" # same repo as `zabbix`
grep -Fq -- '--tag ness-backup-set-20261109T120000-0300' "${RESTIC_STUB_LOG}"
grep -Fq 'dataset=zabbix-cutover' <<<"${out}"

# cutover older than the nightly still wins for zabbix-cutover
rm -rf "${cutover}/20261109T120000-0300"
out="$(run zabbix-cutover)"
grep -Fq 'backup_set_id=20261101T100000-0300' <<<"${out}"

# default dataset is unchanged: nightly only
out="$(run zabbix)"
grep -Fq 'backup_set_id=20261108T220000-0300' <<<"${out}"
grep -Fq "cwd=${nightly}/20261108T220000-0300" "${RESTIC_STUB_LOG}"
grep -Fq '/ness-os/zabbix-prod/zabbix ' "${RESTIC_STUB_LOG}"

# unknown dataset fails and the usage lists the new one
if bash "${tmpdir}/script.sh" backup nope >"${tmpdir}/err" 2>&1; then echo 'unknown dataset accepted' >&2; exit 1; fi
grep -Fq 'zabbix-cutover' "${tmpdir}/err"
echo 'object-storage restic datasets: ok'
