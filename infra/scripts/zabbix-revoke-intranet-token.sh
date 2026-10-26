#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

if [[ ${EUID} -ne 0 ]]; then
  echo "This action must run as root." >&2
  exit 1
fi

readonly zabbix_config="/etc/zabbix/zabbix_server.conf"
readonly evidence_dir="/root/incident-quarantine/20260820-zbx-sys-health/token-revocation-20260821"

[[ ! -e "${evidence_dir}" ]] || {
  echo "Evidence directory already exists; refusing to overwrite it." >&2
  exit 10
}

db_user="$(sed -n 's/^DBUser=//p' "${zabbix_config}" | tail -1)"
db_password="$(sed -n 's/^DBPassword=//p' "${zabbix_config}" | tail -1)"
db_name="$(sed -n 's/^DBName=//p' "${zabbix_config}" | tail -1)"
db_user="${db_user:-zabbix}"
db_name="${db_name:-zabbix}"
export MYSQL_PWD="${db_password}"

token_count="$(mariadb --batch --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="SELECT COUNT(*) FROM token t JOIN users u ON u.userid=t.userid WHERE u.username='resper' AND t.name='intranet'")"
enabled_count="$(mariadb --batch --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="SELECT COUNT(*) FROM token t JOIN users u ON u.userid=t.userid WHERE u.username='resper' AND t.name='intranet' AND t.status=0")"

[[ "${token_count}" == "1" ]] || {
  echo "Expected exactly one resper/intranet token, found ${token_count}; refusing change." >&2
  exit 11
}
[[ "${enabled_count}" == "1" ]] || {
  echo "Expected the resper/intranet token to be enabled exactly once, found ${enabled_count}; refusing change." >&2
  exit 12
}

install -d -o root -g root -m 700 "${evidence_dir}"

mariadb --batch --raw --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT t.tokenid,t.name,u.username,t.status,
           FROM_UNIXTIME(NULLIF(t.created_at,0)),
           FROM_UNIXTIME(NULLIF(t.expires_at,0)),
           FROM_UNIXTIME(NULLIF(t.lastaccess,0)),creator.username
    FROM token t
    JOIN users u ON u.userid=t.userid
    LEFT JOIN users creator ON creator.userid=t.creator_userid
    WHERE u.username='resper' AND t.name='intranet';" \
  > "${evidence_dir}/token-before.tsv"

mariadb --user="${db_user}" --database="${db_name}" \
  --execute="UPDATE token t JOIN users u ON u.userid=t.userid SET t.status=1 WHERE u.username='resper' AND t.name='intranet' AND t.status=0"

enabled_after="$(mariadb --batch --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="SELECT COUNT(*) FROM token t JOIN users u ON u.userid=t.userid WHERE u.username='resper' AND t.name='intranet' AND t.status=0")"
disabled_after="$(mariadb --batch --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="SELECT COUNT(*) FROM token t JOIN users u ON u.userid=t.userid WHERE u.username='resper' AND t.name='intranet' AND t.status=1")"

[[ "${enabled_after}" == "0" && "${disabled_after}" == "1" ]] || {
  echo "Token revocation verification failed." >&2
  exit 20
}

mariadb --batch --raw --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT t.tokenid,t.name,u.username,t.status,
           FROM_UNIXTIME(NULLIF(t.created_at,0)),
           FROM_UNIXTIME(NULLIF(t.expires_at,0)),
           FROM_UNIXTIME(NULLIF(t.lastaccess,0)),creator.username
    FROM token t
    JOIN users u ON u.userid=t.userid
    LEFT JOIN users creator ON creator.userid=t.creator_userid
    WHERE u.username='resper' AND t.name='intranet';" \
  > "${evidence_dir}/token-after.tsv"

cat > "${evidence_dir}/RESULT.txt" <<EOF
completed_at=$(date --iso-8601=seconds)
owner=resper
name=intranet
enabled_before=${enabled_count}
enabled_after=${enabled_after}
disabled_after=${disabled_after}
EOF

find "${evidence_dir}" -type f ! -name SHA256SUMS -print0 \
  | sort -z | xargs -0 sha256sum > "${evidence_dir}/SHA256SUMS"
(
  cd "${evidence_dir}"
  sha256sum -c SHA256SUMS
)
chmod -R go-rwx "${evidence_dir}"

unset MYSQL_PWD db_password
echo "The resper/intranet token is disabled and evidence checksums are valid."
