#!/usr/bin/env bash
set -euo pipefail

readonly ZABBIX_SERVER_CONF=/etc/zabbix/zabbix_server.conf
readonly ZABBIX_WEB_CONF=/etc/zabbix/web/zabbix.conf.php

db_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key { print substr($0, index($0, "=") + 1); exit }' "$ZABBIX_SERVER_CONF"
}

db_name="$(db_value DBName)"
db_user="$(db_value DBUser)"
db_password="$(db_value DBPassword)"

[[ -n "$db_name" && -n "$db_user" && -n "$db_password" ]]

install -d -m 0750 -o root -g www-data /etc/zabbix/web
umask 0077
{
  printf '%s\n' '<?php'
  printf "%s\n" "\$DB['TYPE'] = 'MYSQL';"
  printf "%s\n" "\$DB['SERVER'] = 'localhost';"
  printf "%s\n" "\$DB['PORT'] = '0';"
  printf "%s\n" "\$DB['DATABASE'] = '${db_name}';"
  printf "%s\n" "\$DB['USER'] = '${db_user}';"
  printf "%s\n" "\$DB['PASSWORD'] = '${db_password}';"
  printf "%s\n" "\$DB['SCHEMA'] = '';"
  printf "%s\n" "\$ZBX_SERVER = '127.0.0.1';"
  printf "%s\n" "\$ZBX_SERVER_PORT = '10051';"
  printf "%s\n" "\$ZBX_SERVER_NAME = 'ness.OS Zabbix UAT';"
  printf '%s\n' '$IMAGE_FORMAT_DEFAULT = IMAGE_FORMAT_PNG;'
} >"$ZABBIX_WEB_CONF"
chown root:www-data "$ZABBIX_WEB_CONF"
chmod 0640 "$ZABBIX_WEB_CONF"
