#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

[[ ${EUID} -eq 0 ]] || { echo 'must run as root' >&2; exit 1; }

readonly db_name=dbzabbix
readonly env_file=/etc/ness-os/zabbix-cutover-bootstrap.env
readonly evidence_root=/var/lib/ness-os/restore-evidence
readonly api_url=https://zabbix.ness.com.br/api_jsonrpc.php

[[ -r ${env_file} ]] || { echo 'cutover API environment is unavailable' >&2; exit 2; }
command -v curl >/dev/null
command -v jq >/dev/null
systemctl is-active --quiet apache2
mariadb --protocol=socket -NBe "SELECT 1 FROM ${db_name}.dbversion LIMIT 1;" >/dev/null

token="$(sed -n 's/^ZABBIX_API_TOKEN=//p' "${env_file}" | tail -1)"
[[ ${#token} -ge 32 ]]

install -d -m 0700 -o root -g root "${evidence_root}"
stamp="$(date +%Y%m%dT%H%M%S%z)"
before="${evidence_root}/zabbix-post-cutover-reconcile-before-${stamp}.tsv"
after="${evidence_root}/zabbix-post-cutover-reconcile-after-${stamp}.tsv"

snapshot() {
  local output=${1:?output is required}
  {
    printf 'section\tuserid\tusername\troleid\tuserdirectoryid\n'
    mariadb --protocol=socket --batch --raw --skip-column-names "${db_name}" \
      -e "SELECT 'user',userid,username,roleid,COALESCE(userdirectoryid,0) FROM users ORDER BY userid;"
    printf 'section\tuserdirectoryid\tname\tprovision_status\tscim_status\n'
    mariadb --protocol=socket --batch --raw --skip-column-names "${db_name}" \
      -e "SELECT 'saml',d.userdirectoryid,d.name,d.provision_status,s.scim_status FROM userdirectory d JOIN userdirectory_saml s USING(userdirectoryid) ORDER BY d.userdirectoryid;"
  } >"${output}"
  chmod 0600 "${output}"
}

api_call() {
  local request=${1:?request is required}
  local response
  response="$(curl --fail --silent --show-error \
    --resolve zabbix.ness.com.br:443:127.0.0.1 \
    --header 'Content-Type: application/json-rpc' \
    --header "Authorization: Bearer ${token}" \
    --data-binary "${request}" \
    "${api_url}")"
  if jq -e '.error' >/dev/null <<<"${response}"; then
    jq '.error' <<<"${response}" >&2
    return 1
  fi
  printf '%s\n' "${response}"
}

snapshot "${before}"

# A provisioned user cannot always be changed through user.update. Detach the
# single inherited link while the server is still isolated, then use the API
# for supported role and directory changes.
mariadb --protocol=socket "${db_name}" \
  -e "UPDATE users SET userdirectoryid=NULL WHERE username='akadmin' AND userdirectoryid IS NOT NULL;"

directory_request="$(jq -nc '{
  jsonrpc:"2.0",
  method:"userdirectory.update",
  params:{
    userdirectoryid:"1",
    name:"Authentik - Zabbix Production",
    provision_status:"0",
    scim_status:"0",
    idp_entityid:"https://sso.ness.com.br",
    sso_url:"https://sso.ness.com.br/application/saml/zabbix/",
    slo_url:"https://sso.ness.com.br/application/saml/zabbix/",
    sp_entityid:"https://zabbix.ness.com.br"
  },
  id:1
}')"
api_call "${directory_request}" | jq -e '.result.userdirectoryids == ["1"]' >/dev/null

roles_request="$(jq -nc '{
  jsonrpc:"2.0",
  method:"user.update",
  params:[
    {userid:"1",roleid:"3"},
    {userid:"3",roleid:"3"},
    {userid:"4",roleid:"3"},
    {userid:"29",roleid:"3"},
    {userid:"32",roleid:"3"},
    {userid:"5",roleid:"2"},
    {userid:"6",roleid:"2"},
    {userid:"7",roleid:"2"},
    {userid:"8",roleid:"2"},
    {userid:"9",roleid:"2"},
    {userid:"11",roleid:"2"},
    {userid:"13",roleid:"2"},
    {userid:"30",roleid:"2"},
    {userid:"33",roleid:"2"}
  ],
  id:2
}')"
api_call "${roles_request}" | jq -e '.result.userids | length == 14' >/dev/null

validation_request="$(jq -nc '{
  jsonrpc:"2.0",
  method:"user.get",
  params:{output:["userid","username","roleid","userdirectoryid"],sortfield:"userid"},
  id:3
}')"
api_call "${validation_request}" >/dev/null

snapshot "${after}"

super_admins="$(mariadb --protocol=socket --batch --raw --skip-column-names "${db_name}" \
  -e "SELECT GROUP_CONCAT(username ORDER BY username SEPARATOR ',') FROM users WHERE roleid=3;")"
[[ ${super_admins} == 'Admin,iaraujo,resper,rsalerno,zbxgrafana' ]]

read -r provision_status scim_status idp_entityid sso_url slo_url sp_entityid < <(
  mariadb --protocol=socket --batch --raw --skip-column-names "${db_name}" \
    -e "SELECT d.provision_status,s.scim_status,s.idp_entityid,s.sso_url,s.slo_url,s.sp_entityid FROM userdirectory d JOIN userdirectory_saml s USING(userdirectoryid) WHERE d.userdirectoryid=1;"
)
[[ ${provision_status} == 0 && ${scim_status} == 0 ]]
[[ ${idp_entityid} == 'https://sso.ness.com.br' ]]
[[ ${sso_url} == 'https://sso.ness.com.br/application/saml/zabbix/' ]]
[[ ${slo_url} == 'https://sso.ness.com.br/application/saml/zabbix/' ]]
[[ ${sp_entityid} == 'https://zabbix.ness.com.br' ]]

akadmin_directory="$(mariadb --protocol=socket --batch --raw --skip-column-names "${db_name}" \
  -e "SELECT COALESCE(userdirectoryid,0) FROM users WHERE username='akadmin';")"
[[ ${akadmin_directory} == 0 ]]

printf 'saml_provisioning=disabled\n'
printf 'scim=disabled\n'
printf 'saml_endpoints=production\n'
printf 'super_admins=%s\n' "${super_admins}"
printf 'akadmin_directory=detached\n'
printf 'before=%s\n' "${before}"
printf 'after=%s\n' "${after}"
printf 'reconcile=PASS\n'

unset token
