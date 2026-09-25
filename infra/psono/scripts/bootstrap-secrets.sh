#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly stack_dir="${PSONO_STACK_DIR:-/opt/ness-os-psono}"
readonly env_file="${PSONO_ENV_FILE:-/etc/ness-os/psono.env}"
readonly image='psono/psono-combo:latest@sha256:0266a866addd08e7ad364ffe457bb499815a6941744251012a0e2eae506575fd'

[[ -f ${stack_dir}/docker-compose.yml ]] || { echo 'psono stack is unavailable' >&2; exit 2; }
[[ ! -e ${env_file} ]] || { echo 'psono env already exists; refusing to overwrite' >&2; exit 3; }

install -d -m 0700 -o root -g root "$(dirname "${env_file}")"
keys_file="$(mktemp)"
trap 'rm -f "${keys_file}"' EXIT

docker run --rm "${image}" python3 ./psono/manage.py generateserverkeys >"${keys_file}"

read_key() {
  local name="$1"
  sed -n "s/^${name}:[[:space:]]*'\(.*\)'[[:space:]]*$/\1/p" "${keys_file}"
}

secret_key="$(read_key SECRET_KEY)"
activation_link_secret="$(read_key ACTIVATION_LINK_SECRET)"
db_secret="$(read_key DB_SECRET)"
email_secret_salt="$(read_key EMAIL_SECRET_SALT)"
private_key="$(read_key PRIVATE_KEY)"
public_key="$(read_key PUBLIC_KEY)"

for value in \
  "${secret_key}" "${activation_link_secret}" "${db_secret}" \
  "${email_secret_salt}" "${private_key}" "${public_key}"; do
  [[ -n ${value} && ${value} != *"'"* && ${value} != *$'\n'* ]] || {
    echo 'generated Psono key output is invalid' >&2
    exit 4
  }
done

cat >"${env_file}" <<EOF
PSONO_DOMAIN=cofre.ness.com.br
PSONO_ALLOWED_DOMAIN=ness.com.br
PSONO_SECRET_KEY='${secret_key}'
PSONO_ACTIVATION_LINK_SECRET='${activation_link_secret}'
PSONO_DB_SECRET='${db_secret}'
PSONO_EMAIL_SECRET_SALT='${email_secret_salt}'
PSONO_PRIVATE_KEY='${private_key}'
PSONO_PUBLIC_KEY='${public_key}'
POSTGRES_PASSWORD='$(openssl rand -hex 32)'
PSONO_EMAIL_FROM='ness. cofre <cofre@ness.com.br>'
PSONO_SMTP_ENABLED=false
PSONO_ALLOW_REGISTRATION=false
PSONO_ALLOW_LOST_PASSWORD=false
PSONO_MULTIFACTOR_ENABLED=false
EOF

chmod 0600 "${env_file}"
unset secret_key activation_link_secret db_secret email_secret_salt private_key public_key
echo 'psono secret bootstrap=PASS smtp=disabled registration=disabled'
