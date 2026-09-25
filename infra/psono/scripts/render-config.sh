#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly env_file="${PSONO_ENV_FILE:-/etc/ness-os/psono.env}"
readonly output_dir="${PSONO_RUNTIME_DIR:-/opt/ness-os-psono/runtime}"
readonly branding_dir="${PSONO_BRANDING_DIR:-/opt/ness-os-psono/branding}"

[[ -f ${env_file} && ! -L ${env_file} ]] || { echo 'psono env file is unavailable' >&2; exit 2; }
[[ $(stat -c '%u:%a' "${env_file}") =~ ^0:(400|600)$ ]] || {
  echo 'psono env file must be root-owned and mode 0400 or 0600' >&2
  exit 3
}

set -a
# shellcheck disable=SC1090
. "${env_file}"
set +a

required=(
  PSONO_DOMAIN PSONO_ALLOWED_DOMAIN PSONO_SECRET_KEY
  PSONO_ACTIVATION_LINK_SECRET PSONO_DB_SECRET PSONO_EMAIL_SECRET_SALT
  PSONO_PRIVATE_KEY PSONO_PUBLIC_KEY POSTGRES_PASSWORD
  PSONO_EMAIL_FROM
)
for name in "${required[@]}"; do
  [[ -n ${!name:-} ]] || { echo "required variable is absent: ${name}" >&2; exit 4; }
  case ${!name} in
    *"'"*|*$'\n'*) echo "unsafe character in variable: ${name}" >&2; exit 5 ;;
  esac
done

allow_registration="${PSONO_ALLOW_REGISTRATION:-true}"
[[ ${allow_registration} == true || ${allow_registration} == false ]] || {
  echo 'PSONO_ALLOW_REGISTRATION must be true or false' >&2
  exit 6
}

allow_lost_password="${PSONO_ALLOW_LOST_PASSWORD:-true}"
[[ ${allow_lost_password} == true || ${allow_lost_password} == false ]] || {
  echo 'PSONO_ALLOW_LOST_PASSWORD must be true or false' >&2
  exit 7
}

smtp_enabled="${PSONO_SMTP_ENABLED:-true}"
[[ ${smtp_enabled} == true || ${smtp_enabled} == false ]] || {
  echo 'PSONO_SMTP_ENABLED must be true or false' >&2
  exit 8
}
if [[ ${smtp_enabled} == true && -z ${RESEND_API_KEY:-} ]]; then
  echo 'RESEND_API_KEY is required when SMTP is enabled' >&2
  exit 9
fi

multifactor_enabled="${PSONO_MULTIFACTOR_ENABLED:-false}"
[[ ${multifactor_enabled} == true || ${multifactor_enabled} == false ]] || {
  echo 'PSONO_MULTIFACTOR_ENABLED must be true or false' >&2
  exit 10
}

readonly logo_file="${branding_dir}/logo.png"
readonly logo_inverse_file="${branding_dir}/logo-inverse.png"
for asset in "${logo_file}" "${logo_inverse_file}"; do
  [[ -f ${asset} && ! -L ${asset} ]] || {
    echo "approved branding asset is unavailable: ${asset}" >&2
    exit 10
  }
done

readonly logo_data="$(base64 -w 0 "${logo_file}")"
readonly logo_inverse_data="$(base64 -w 0 "${logo_inverse_file}")"

install -d -m 0700 -o root -g root "${output_dir}"

cat >"${output_dir}/settings.yaml" <<EOF
SECRET_KEY: '${PSONO_SECRET_KEY}'
ACTIVATION_LINK_SECRET: '${PSONO_ACTIVATION_LINK_SECRET}'
DB_SECRET: '${PSONO_DB_SECRET}'
EMAIL_SECRET_SALT: '${PSONO_EMAIL_SECRET_SALT}'
PRIVATE_KEY: '${PSONO_PRIVATE_KEY}'
PUBLIC_KEY: '${PSONO_PUBLIC_KEY}'
WEB_CLIENT_URL: 'https://${PSONO_DOMAIN}'
HOST_URL: 'https://${PSONO_DOMAIN}/server'
NUM_PROXIES: 2
DEBUG: false
ALLOWED_HOSTS: ['${PSONO_DOMAIN}']
ALLOWED_DOMAINS: ['${PSONO_ALLOWED_DOMAIN}']
ALLOW_REGISTRATION: ${allow_registration}
ALLOW_LOST_PASSWORD: ${allow_lost_password}
MANAGEMENT_ENABLED: true
MULTIFACTOR_ENABLED: ${multifactor_enabled}
ALLOWED_SECOND_FACTORS: ['google_authenticator', 'webauthn']
DATABASES:
  default:
    ENGINE: 'django.db.backends.postgresql_psycopg2'
    NAME: 'psono'
    USER: 'psono'
    PASSWORD: '${POSTGRES_PASSWORD}'
    HOST: 'database'
    PORT: '5432'
EMAIL_FROM: '${PSONO_EMAIL_FROM}'
EOF

if [[ ${smtp_enabled} == true ]]; then
  cat >>"${output_dir}/settings.yaml" <<EOF
EMAIL_HOST: 'smtp.resend.com'
EMAIL_HOST_USER: 'resend'
EMAIL_HOST_PASSWORD: '${RESEND_API_KEY}'
EMAIL_PORT: 587
EMAIL_USE_TLS: true
EMAIL_USE_SSL: false
EMAIL_TIMEOUT: 10
EOF
else
  cat >>"${output_dir}/settings.yaml" <<EOF
EMAIL_HOST: '127.0.0.1'
EMAIL_HOST_USER: ''
EMAIL_HOST_PASSWORD: ''
EMAIL_PORT: 25
EMAIL_USE_TLS: false
EMAIL_USE_SSL: false
EMAIL_TIMEOUT: 3
EOF
fi

cat >"${output_dir}/config.json" <<EOF
{
  "backend_servers": [{"title": "ness. cofre", "url": "https://${PSONO_DOMAIN}/server"}],
  "base_url": "https://${PSONO_DOMAIN}/",
  "allow_custom_server": false,
  "allow_registration": ${allow_registration},
  "allow_lost_password": ${allow_lost_password},
  "logo": "data:image/png;base64,${logo_data}",
  "logo_inverse": "data:image/png;base64,${logo_inverse_data}",
  "theme": {
    "spacing": 8,
    "palette": {
      "background": {
        "default": "#f8fafc",
        "paper": "#ffffff"
      },
      "action": {
        "disabled": "rgba(255, 255, 255, 0.72)",
        "disabledBackground": "rgba(0, 173, 232, 0.42)"
      },
      "primary": {
        "main": "#00ade8",
        "contrastText": "#000000"
      },
      "secondary": {
        "main": "#000000",
        "contrastText": "#ffffff"
      },
      "checked": {
        "main": "#00ade8",
        "light": "#00ade8",
        "dark": "#00ade8",
        "contrastText": "#000000"
      },
      "appBarText": {
        "main": "#ffffff",
        "light": "#ffffff",
        "dark": "#ffffff",
        "contrastText": "#000000"
      },
      "appBarBackground": {
        "main": "#000000",
        "light": "#000000",
        "dark": "#000000",
        "contrastText": "#ffffff"
      },
      "blueBackground": {
        "main": "#151f2b",
        "light": "#151f2b",
        "dark": "#151f2b",
        "contrastText": "#ffffff"
      },
      "baseBackground": {
        "main": "#f8fafc",
        "light": "#f8fafc",
        "dark": "#f8fafc",
        "contrastText": "#000000"
      },
      "lightBackground": {
        "main": "#ffffff",
        "light": "#ffffff",
        "dark": "#ffffff",
        "contrastText": "#000000"
      },
      "baseTitleBackground": {
        "main": "#ffffff",
        "light": "#ffffff",
        "dark": "#ffffff",
        "contrastText": "#000000"
      }
    },
    "transitions": {
      "easing": {
        "easeInOut": "cubic-bezier(0.2, 0, 0, 1)",
        "easeOut": "cubic-bezier(0.2, 0, 0, 1)",
        "easeIn": "cubic-bezier(0.2, 0, 0, 1)",
        "sharp": "cubic-bezier(0.2, 0, 0, 1)"
      }
    },
    "components": {
      "MuiPaper": {
        "styleOverrides": {
          "root": {
            "boxShadow": "0 8px 24px rgba(0, 0, 0, 0.12)"
          }
        }
      },
      "MuiButton": {
        "styleOverrides": {
          "containedPrimary": {
            "color": "#000000"
          }
        }
      }
    }
  }
}
EOF

cat >"${output_dir}/postgres.env" <<EOF
POSTGRES_PASSWORD='${POSTGRES_PASSWORD}'
EOF

chmod 0600 \
  "${output_dir}/settings.yaml" \
  "${output_dir}/postgres.env"
chmod 0644 "${output_dir}/config.json"
echo 'psono runtime configuration rendered without printing secret values'
