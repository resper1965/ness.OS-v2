#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }
readonly db=dbzabbix
readonly username=ness_uat_breakglass
readonly password_file=/tmp/zabbix-uat-breakglass.password

[[ -s "${password_file}" && ! -L "${password_file}" ]] || { echo 'missing password input' >&2; exit 1; }
password_hash="$(php -r 'echo password_hash(trim(file_get_contents($argv[1])), PASSWORD_BCRYPT);' "${password_file}")"

mariadb --protocol=socket "${db}" <<SQL
START TRANSACTION;
DELETE FROM users_groups WHERE userid IN (SELECT userid FROM users WHERE username = '${username}');
DELETE FROM users WHERE username = '${username}';
INSERT INTO users (userid, username, name, surname, passwd, roleid)
SELECT COALESCE(MAX(userid), 0) + 1, '${username}', 'UAT', 'Breakglass', '${password_hash}', 3 FROM users;
INSERT INTO users_groups (id, usrgrpid, userid)
SELECT (SELECT COALESCE(MAX(id), 0) + 1 FROM users_groups), 7, userid FROM users WHERE username = '${username}';
COMMIT;
SQL

rm -f "${password_file}"
mariadb --protocol=socket --batch --skip-column-names "${db}" -e "SELECT u.username, r.name, g.name FROM users u JOIN role r ON r.roleid=u.roleid JOIN users_groups ug ON ug.userid=u.userid JOIN usrgrp g ON g.usrgrpid=ug.usrgrpid WHERE u.username='${username}';"
