#!/usr/bin/env bash
set -Eeuo pipefail

readonly certificate_path="${1:?certificate path is required}"
readonly private_key_path="${2:?private-key path is required}"

[[ -s "${certificate_path}" && -s "${private_key_path}" ]]
certificate_modulus="$(openssl x509 -noout -modulus -in "${certificate_path}" | openssl sha256)"
key_modulus="$(openssl rsa -noout -modulus -in "${private_key_path}" | openssl sha256)"
[[ "${certificate_modulus}" == "${key_modulus}" ]]
openssl x509 -in "${certificate_path}" -noout -subject -dates
echo 'certificate_key_match=PASS'
