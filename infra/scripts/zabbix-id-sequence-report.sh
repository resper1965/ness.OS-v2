#!/usr/bin/env bash
set -euo pipefail

# Read-only report for Zabbix application-managed ID counters.
[[ ${EUID} -eq 0 ]] || {
    echo 'must run as root' >&2
    exit 1
}

readonly zabbix_config=/etc/zabbix/zabbix_server.conf
db_user="$(sed -n 's/^DBUser=//p' "${zabbix_config}" | tail -1)"
db_password="$(sed -n 's/^DBPassword=//p' "${zabbix_config}" | tail -1)"
db_name="$(sed -n 's/^DBName=//p' "${zabbix_config}" | tail -1)"
db_user="${db_user:-zabbix}"
db_name="${db_name:-zabbix}"
export MYSQL_PWD="${db_password}"
unset db_password

mariadb --protocol=socket --batch --raw --skip-column-names \
    --user="${db_user}" --database="${db_name}" <<'SQL'
SELECT 'sequence', 'role', 'roleid', COALESCE(MAX(roleid), 0),
       COALESCE((SELECT nextid FROM ids WHERE table_name='role' AND field_name='roleid'), -1)
  FROM role
UNION ALL
SELECT 'sequence', 'usrgrp', 'usrgrpid', COALESCE(MAX(usrgrpid), 0),
       COALESCE((SELECT nextid FROM ids WHERE table_name='usrgrp' AND field_name='usrgrpid'), -1)
  FROM usrgrp
UNION ALL
SELECT 'sequence', 'users', 'userid', COALESCE(MAX(userid), 0),
       COALESCE((SELECT nextid FROM ids WHERE table_name='users' AND field_name='userid'), -1)
  FROM users
UNION ALL
SELECT 'sequence', 'users_groups', 'id', COALESCE(MAX(id), 0),
       COALESCE((SELECT nextid FROM ids WHERE table_name='users_groups' AND field_name='id'), -1)
  FROM users_groups
UNION ALL
SELECT 'sequence', 'token', 'tokenid', COALESCE(MAX(tokenid), 0),
       COALESCE((SELECT nextid FROM ids WHERE table_name='token' AND field_name='tokenid'), -1)
  FROM token
UNION ALL
SELECT 'sequence', 'rights', 'rightid', COALESCE(MAX(rightid), 0),
       COALESCE((SELECT nextid FROM ids WHERE table_name='rights' AND field_name='rightid'), -1)
  FROM rights;
SQL

unset MYSQL_PWD
