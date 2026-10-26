#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly stack_dir="${PSONO_STACK_DIR:-/opt/ness-os-psono}"
readonly env_file="${PSONO_ENV_FILE:-/etc/ness-os/psono.env}"
readonly username="${PSONO_BOOTSTRAP_USERNAME:-resper@ness.com.br}"
readonly credentials_file="${PSONO_BOOTSTRAP_CREDENTIALS_FILE:-/root/ness-psono-bootstrap-credentials}"

[[ ${username} == *@ness.com.br ]] || { echo 'bootstrap username must use ness.com.br' >&2; exit 2; }
[[ -f ${env_file} ]] || { echo 'psono env is unavailable' >&2; exit 3; }
[[ ! -e ${credentials_file} ]] || { echo 'bootstrap credentials already exist; refusing to overwrite' >&2; exit 4; }

set -a
# shellcheck disable=SC1090
. "${env_file}"
set +a

password="$(openssl rand -hex 24)"
compose=(docker compose -f docker-compose.yml -f docker-compose.aiops.yml)

cd "${stack_dir}"
"${compose[@]}" run --rm --no-deps psono \
  python3 ./psono/manage.py createuser "${username}" "${password}" "${username}" >/dev/null
"${compose[@]}" run --rm --no-deps psono \
  python3 ./psono/manage.py promoteuser "${username}" superuser >/dev/null

cat >"${credentials_file}" <<EOF
PSONO_URL=https://cofre.ness.com.br
PSONO_USERNAME=${username}
PSONO_BOOTSTRAP_PASSWORD=${password}
EOF
chmod 0600 "${credentials_file}"
unset password
echo "psono bootstrap admin=PASS username=${username} credentials=${credentials_file}"
