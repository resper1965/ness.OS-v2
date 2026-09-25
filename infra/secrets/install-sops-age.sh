#!/usr/bin/env bash
# Installs the approved SOPS/age binaries without replacing existing tooling.
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly sops_version='3.13.3'
readonly sops_sha256='e5bec3346a873ae91d871550f3e698c1aad962aff462a080e40f25fde17fef6b'
readonly age_version='1.3.2'
readonly age_sha256='cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10'
readonly bin_dir='/usr/local/bin'

for command in curl install mktemp sha256sum tar uname; do
  command -v "${command}" >/dev/null || { echo "missing command: ${command}" >&2; exit 2; }
done
[[ $(uname -m) == x86_64 ]] || { echo 'only x86_64 is approved by this installer' >&2; exit 3; }

expected_tools=("${bin_dir}/sops" "${bin_dir}/age" "${bin_dir}/age-keygen")
existing=0
for tool in "${expected_tools[@]}"; do
  [[ ! -e ${tool} ]] || existing=$((existing + 1))
done
if (( existing > 0 )); then
  if [[ $(command -v sops 2>/dev/null || true) == "${bin_dir}/sops" ]] &&
     [[ $(command -v age 2>/dev/null || true) == "${bin_dir}/age" ]] &&
     [[ $(command -v age-keygen 2>/dev/null || true) == "${bin_dir}/age-keygen" ]] &&
     sops --version 2>/dev/null | grep -Fq "${sops_version}" &&
     age --version 2>/dev/null | grep -Fq "${age_version}"; then
    echo "sops_age_install=ALREADY_CURRENT sops=${sops_version} age=${age_version}"
    exit 0
  fi
  echo 'existing SOPS/age tooling differs; refusing to overwrite' >&2
  exit 4
fi

work_dir="$(mktemp -d /tmp/ness-sops-age.XXXXXX)"
[[ ${work_dir} == /tmp/ness-sops-age.* && -d ${work_dir} ]] || {
  echo 'unexpected temporary directory' >&2
  exit 5
}
trap '[[ ${work_dir} == /tmp/ness-sops-age.* ]] && rm -rf -- "${work_dir}"' EXIT

readonly sops_asset="${work_dir}/sops"
readonly age_archive="${work_dir}/age.tar.gz"
curl --fail --silent --show-error --location --retry 3 \
  --output "${sops_asset}" \
  "https://github.com/getsops/sops/releases/download/v${sops_version}/sops-v${sops_version}.linux.amd64"
curl --fail --silent --show-error --location --retry 3 \
  --output "${age_archive}" \
  "https://github.com/FiloSottile/age/releases/download/v${age_version}/age-v${age_version}-linux-amd64.tar.gz"

printf '%s  %s\n' "${sops_sha256}" "${sops_asset}" | sha256sum --check --status
printf '%s  %s\n' "${age_sha256}" "${age_archive}" | sha256sum --check --status
tar --extract --gzip --file "${age_archive}" --directory "${work_dir}"
[[ -x ${work_dir}/age/age && -x ${work_dir}/age/age-keygen ]] || {
  echo 'age archive does not contain the expected binaries' >&2
  exit 6
}

install -o root -g root -m 0755 "${sops_asset}" "${bin_dir}/sops"
install -o root -g root -m 0755 "${work_dir}/age/age" "${bin_dir}/age"
install -o root -g root -m 0755 "${work_dir}/age/age-keygen" "${bin_dir}/age-keygen"

sops --version | grep -Fq "${sops_version}"
age --version | grep -Fq "${age_version}"
age-keygen --version | grep -Fq "${age_version}"
echo "sops_age_install=PASS sops=${sops_version} age=${age_version}"
