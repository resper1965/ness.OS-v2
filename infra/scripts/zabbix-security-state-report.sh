#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

if [[ ${EUID} -ne 0 ]]; then
  echo "This report must run as root." >&2
  exit 1
fi

readonly zabbix_config="/etc/zabbix/zabbix_server.conf"
db_user="$(sed -n 's/^DBUser=//p' "${zabbix_config}" | tail -1)"
db_password="$(sed -n 's/^DBPassword=//p' "${zabbix_config}" | tail -1)"
db_name="$(sed -n 's/^DBName=//p' "${zabbix_config}" | tail -1)"
db_user="${db_user:-zabbix}"
db_name="${db_name:-zabbix}"
export MYSQL_PWD="${db_password}"

echo "SERVER_POLICY_BEGIN"
grep -E '^(EnableGlobalScripts|LogRemoteCommands|AllowKey|DenyKey)=' "${zabbix_config}" || true
echo "SERVER_POLICY_END"

echo "USERS_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT u.userid,u.username,u.name,u.surname,r.name,r.type,
           u.attempt_failed,FROM_UNIXTIME(NULLIF(u.attempt_clock,0))
    FROM users u
    JOIN role r ON r.roleid=u.roleid
    ORDER BY r.type DESC,u.username;"
echo "USERS_END"

echo "USER_GROUPS_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT u.userid,u.username,g.usrgrpid,g.name,g.gui_access,g.users_status
    FROM users u
    JOIN users_groups ug ON ug.userid=u.userid
    JOIN usrgrp g ON g.usrgrpid=ug.usrgrpid
    ORDER BY u.username,g.name;"
echo "USER_GROUPS_END"

echo "SESSIONS_BY_USER_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT u.userid,u.username,COUNT(s.sessionid),
           SUM(CASE WHEN s.status=0 THEN 1 ELSE 0 END),
           FROM_UNIXTIME(MAX(s.lastaccess))
    FROM users u
    LEFT JOIN sessions s ON s.userid=u.userid
    GROUP BY u.userid,u.username
    HAVING COUNT(s.sessionid)>0
    ORDER BY COUNT(s.sessionid) DESC;"
echo "SESSIONS_BY_USER_END"

echo "TOKENS_BY_USER_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT u.userid,u.username,COUNT(t.tokenid),
           SUM(CASE WHEN t.status=0 THEN 1 ELSE 0 END),
           FROM_UNIXTIME(MAX(t.lastaccess))
    FROM users u
    LEFT JOIN token t ON t.userid=u.userid
    GROUP BY u.userid,u.username
    HAVING COUNT(t.tokenid)>0
    ORDER BY COUNT(t.tokenid) DESC;"
echo "TOKENS_BY_USER_END"

echo "TOKEN_METADATA_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT t.tokenid,t.name,u.username,t.status,
           FROM_UNIXTIME(NULLIF(t.created_at,0)),
           FROM_UNIXTIME(NULLIF(t.expires_at,0)),
           FROM_UNIXTIME(NULLIF(t.lastaccess,0)),
           creator.username
    FROM token t
    JOIN users u ON u.userid=t.userid
    LEFT JOIN users creator ON creator.userid=t.creator_userid
    ORDER BY t.tokenid;"
echo "TOKEN_METADATA_END"

echo "SCRIPT_SUMMARY_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT COUNT(*),
           SUM(execute_on=1),
           SUM(name REGEXP '^(MyScripttest|AutoRCE_|_d|cron_health_|chk3)'),
           SUM(LOWER(command) REGEXP 'xmrig|zbx_cron_health|zbx_sys_health')
    FROM scripts;"
echo "SCRIPT_SUMMARY_END"

echo "SUSPICIOUS_SCRIPT_METADATA_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT scriptid,name,type,execute_on,scope,CHAR_LENGTH(command),SHA2(command,256)
    FROM scripts
    WHERE name REGEXP '^(MyScripttest|AutoRCE_|_d|cron_health_|chk3)'
    ORDER BY scriptid;"
echo "SUSPICIOUS_SCRIPT_METADATA_END"

echo "ALL_SCRIPT_METADATA_BEGIN"
mariadb --batch --raw --skip-column-names \
  --user="${db_user}" --database="${db_name}" \
  --execute="
    SELECT scriptid,name,type,execute_on,scope,CHAR_LENGTH(command),SHA2(command,256)
    FROM scripts
    ORDER BY scriptid;"
echo "ALL_SCRIPT_METADATA_END"

unset MYSQL_PWD db_password
