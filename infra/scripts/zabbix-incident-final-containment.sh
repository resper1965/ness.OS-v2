#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

if [[ ${EUID} -ne 0 ]]; then
  echo "This containment must run as root." >&2
  exit 1
fi

readonly zabbix_config="/etc/zabbix/zabbix_server.conf"
readonly incident_root="/root/incident-quarantine/20260820-zbx-sys-health"
readonly existing_evidence="${incident_root}/db-evidence"
readonly containment_evidence="${incident_root}/final-containment-20260821"

grep -qx 'EnableGlobalScripts=0' "${zabbix_config}" || {
  echo "EnableGlobalScripts=0 is not active; refusing containment." >&2
  exit 10
}

(
  cd "${existing_evidence}"
  sha256sum -c SHA256SUMS
)

db_user="$(sed -n 's/^DBUser=//p' "${zabbix_config}" | tail -1)"
db_password="$(sed -n 's/^DBPassword=//p' "${zabbix_config}" | tail -1)"
db_name="$(sed -n 's/^DBName=//p' "${zabbix_config}" | tail -1)"
db_user="${db_user:-zabbix}"
db_name="${db_name:-zabbix}"
export MYSQL_PWD="${db_password}"

custom_script_count="$(mariadb --batch --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="SELECT COUNT(*) FROM scripts WHERE scriptid>=26")"
admin_session_count="$(mariadb --batch --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="SELECT COUNT(*) FROM sessions WHERE userid=1")"
admin_token_count="$(mariadb --batch --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="SELECT COUNT(*) FROM token WHERE userid=1")"

[[ "${custom_script_count}" == "58" ]] || {
  echo "Expected 58 custom scripts, found ${custom_script_count}; refusing change." >&2
  exit 11
}
[[ "${admin_session_count}" == "0" ]] || {
  echo "Admin has ${admin_session_count} sessions; refusing change." >&2
  exit 12
}
[[ "${admin_token_count}" == "0" ]] || {
  echo "Admin has ${admin_token_count} tokens; refusing change." >&2
  exit 13
}

install -d -o root -g root -m 700 "${containment_evidence}"

mariadb-dump --user="${db_user}" --single-transaction --quick \
  --no-create-info --skip-triggers --where='scriptid>=26' \
  "${db_name}" scripts | gzip -9 > "${containment_evidence}/custom-scripts-before.sql.gz"

mariadb --batch --raw --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="SELECT scriptid,name,type,execute_on,scope,CHAR_LENGTH(command),SHA2(command,256) FROM scripts WHERE scriptid>=26 ORDER BY scriptid" \
  > "${containment_evidence}/custom-scripts-before.tsv"

mariadb --user="${db_user}" --database="${db_name}" <<'SQL'
START TRANSACTION;
SET @next_users_groups_id := (SELECT COALESCE(MAX(id),0)+1 FROM users_groups);
INSERT INTO users_groups (id,usrgrpid,userid)
SELECT @next_users_groups_id,9,1
WHERE NOT EXISTS (SELECT 1 FROM users_groups WHERE usrgrpid=9 AND userid=1);
UPDATE scripts SET command='true' WHERE scriptid>=26 AND command<>'true';
COMMIT;
SQL

disabled_membership_count="$(mariadb --batch --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="SELECT COUNT(*) FROM users_groups WHERE usrgrpid=9 AND userid=1")"
non_neutral_script_count="$(mariadb --batch --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="SELECT COUNT(*) FROM scripts WHERE scriptid>=26 AND command<>'true'")"

[[ "${disabled_membership_count}" == "1" ]] || {
  echo "Admin was not added exactly once to Disabled." >&2
  exit 20
}
[[ "${non_neutral_script_count}" == "0" ]] || {
  echo "${non_neutral_script_count} custom scripts remain non-neutral." >&2
  exit 21
}

mariadb --batch --raw --skip-column-names --user="${db_user}" --database="${db_name}" \
  --execute="SELECT scriptid,name,type,execute_on,scope,CHAR_LENGTH(command),SHA2(command,256) FROM scripts WHERE scriptid>=26 ORDER BY scriptid" \
  > "${containment_evidence}/custom-scripts-after.tsv"

cat > "${containment_evidence}/RESULT.txt" <<EOF
completed_at=$(date --iso-8601=seconds)
custom_scripts=${custom_script_count}
non_neutral_scripts_after=${non_neutral_script_count}
admin_disabled_memberships=${disabled_membership_count}
admin_sessions=${admin_session_count}
admin_tokens=${admin_token_count}
global_scripts=disabled
EOF

gzip -t "${containment_evidence}/custom-scripts-before.sql.gz"
find "${containment_evidence}" -type f ! -name SHA256SUMS -print0 \
  | sort -z | xargs -0 sha256sum > "${containment_evidence}/SHA256SUMS"
sha256sum -c "${containment_evidence}/SHA256SUMS"
chmod -R go-rwx "${containment_evidence}"

unset MYSQL_PWD db_password
echo "Final incident containment completed."
