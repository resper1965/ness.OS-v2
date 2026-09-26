#!/usr/bin/env bash
set -euo pipefail

# Read-only Zabbix API identity report. Token values and hashes are omitted.
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
SELECT 'token_count', COUNT(*) FROM token;
SELECT 'token', t.tokenid, t.name, t.userid, u.username, t.status,
       CASE WHEN t.expires_at = 0 THEN 'never'
            ELSE FROM_UNIXTIME(t.expires_at) END,
       FROM_UNIXTIME(t.created_at), t.creator_userid
  FROM token t
  LEFT JOIN users u ON u.userid = t.userid
 ORDER BY t.tokenid;
SELECT 'candidate_user', u.userid, u.username, u.name, u.surname,
       u.roleid, r.name, u.attempt_failed
  FROM users u
  LEFT JOIN role r ON r.roleid = u.roleid
 WHERE LOWER(u.username) REGEXP 'api|aiops|ness|svc|service'
 ORDER BY u.userid;
SELECT 'candidate_group', ug.userid, ug.usrgrpid, g.name, g.users_status
  FROM users_groups ug
  JOIN usrgrp g ON g.usrgrpid = ug.usrgrpid
 WHERE ug.userid IN (
       SELECT userid FROM users
        WHERE LOWER(username) REGEXP 'api|aiops|ness|svc|service'
 )
 ORDER BY ug.userid, ug.usrgrpid;
SELECT 'candidate_host_right', ug.userid, r.id, hg.groupid, hg.name, r.permission
  FROM users_groups ug
  JOIN rights r ON r.id = ug.usrgrpid
  JOIN hstgrp hg ON hg.groupid = r.groupid
 WHERE ug.userid IN (
       SELECT userid FROM users
        WHERE LOWER(username) REGEXP 'api|aiops|ness|svc|service'
 )
 ORDER BY ug.userid, hg.name;
SELECT 'role_rule', roleid, type, name, value_int, COALESCE(value_str, '')
  FROM role_rule
 ORDER BY roleid, type, name, value_int, value_str;
SQL

unset MYSQL_PWD
