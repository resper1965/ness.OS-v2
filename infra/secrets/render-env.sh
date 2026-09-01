#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }
command -v sops >/dev/null || { echo 'sops is not installed' >&2; exit 2; }

readonly encrypted="${1:?usage: render-env.sh ENCRYPTED_FILE DESTINATION}"
readonly destination="${2:?usage: render-env.sh ENCRYPTED_FILE DESTINATION}"

[[ -f ${encrypted} && ! -L ${encrypted} ]] || { echo 'encrypted source is unavailable' >&2; exit 3; }
case ${destination} in
  /etc/ness-os/*.env|/run/ness-os/*.env) ;;
  *) echo 'destination must be an explicit ness-os env path' >&2; exit 4 ;;
esac

destination_dir="$(dirname "${destination}")"
install -d -m 0700 -o root -g root "${destination_dir}"
temporary="$(mktemp "${destination_dir}/.rendered.XXXXXX")"
trap 'rm -f -- "${temporary}"' EXIT

sops --decrypt --output-type dotenv "${encrypted}" >"${temporary}"
[[ -s ${temporary} ]] || { echo 'rendered environment is empty' >&2; exit 5; }
chmod 0600 "${temporary}"
chown root:root "${temporary}"
mv -f -- "${temporary}" "${destination}"
trap - EXIT
echo "rendered_env=${destination}"
