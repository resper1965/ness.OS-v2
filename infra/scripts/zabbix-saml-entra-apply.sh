#!/usr/bin/env bash
# Roda NA VPS do Zabbix, como root, DEPOIS do restore e ANTES de apontar o DNS.
# Refaz o SAML do Entra (o restore sobrescreve o banco): IdP, certificado, usuario = e-mail,
# bloqueio da senha local dos usuarios SSO e, opcionalmente, nova senha do akadmin (quebra de vidro).
# Sem --apply so imprime o SQL. Config (nao versionada): /etc/ness-os/zabbix-saml.env, ver .example.
# uso: zabbix-saml-entra-apply.sh [--apply]
set -Eeuo pipefail
apply=0; [[ ${1:-} == --apply ]] && apply=1
cfg="${ZBX_SAML_CONFIG:-/etc/ness-os/zabbix-saml.env}"
[[ -f $cfg ]] || { echo "sem $cfg" >&2; exit 2; }
# shellcheck disable=SC1090
. "$cfg"
: "${TENANT_ID:?}" "${DOMAIN:?}" "${SP_ENTITY:?}" "${CERT_SRC:?}" "${SSO_USERS:?}"
LOCK_USERS="${LOCK_USERS:-$SSO_USERS}"
MYSQL="${ZBX_MYSQL:-mariadb --protocol=socket dbzabbix -B}"
WEBCONF="${ZBX_WEB_CONF:-/etc/zabbix/web/zabbix.conf.php}"
CERT_DST="${ZBX_CERT_DST:-/usr/share/zabbix/conf/certs/idp.crt}"
BACKUP="${ZBX_BACKUP_DIR:-/root/saml-apply-$(date +%Y%m%dT%H%M%S)}"
[[ $TENANT_ID =~ ^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$ ]] || { echo "TENANT_ID invalido" >&2; exit 2; }
[[ $DOMAIN =~ ^[a-z0-9.-]+$ ]] || { echo "DOMAIN invalido" >&2; exit 2; }
[[ $SP_ENTITY =~ ^https://[a-z0-9.-]+$ ]] || { echo "SP_ENTITY invalido" >&2; exit 2; }
for u in $SSO_USERS $LOCK_USERS; do [[ $u =~ ^[a-z0-9._-]+$ ]] || { echo "usuario invalido: $u" >&2; exit 2; }; done
for u in $LOCK_USERS; do [[ " $SSO_USERS " == *" $u "* ]] || { echo "LOCK_USERS fora de SSO_USERS: $u" >&2; exit 2; }; done
[[ -f $CERT_SRC ]] || { echo "sem $CERT_SRC" >&2; exit 2; }
openssl x509 -in "$CERT_SRC" -noout -checkend 0 || { echo "certificado vencido/invalido" >&2; exit 2; }

hash() { if [[ -n ${ZBX_HASH_BIN:-} ]]; then "$ZBX_HASH_BIN"; else php -r 'echo password_hash(trim(stream_get_contents(STDIN)), PASSWORD_BCRYPT);'; fi; }
rnd() { head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; }

sql="UPDATE userdirectory SET provision_status=0 WHERE userdirectoryid=1;
UPDATE userdirectory_saml SET idp_entityid='https://sts.windows.net/$TENANT_ID/', sso_url='https://login.microsoftonline.com/$TENANT_ID/saml2', slo_url='https://login.microsoftonline.com/$TENANT_ID/saml2', username_attribute='user_email', sp_entityid='$SP_ENTITY', nameid_format='', sign_messages=0, sign_assertions=1, sign_authn_requests=0, group_name='', user_username='', user_lastname='', scim_status=0 WHERE userdirectoryid=1;
UPDATE config SET saml_auth_enabled=1;
"
for u in $SSO_USERS; do
  sql+="UPDATE users SET username='$u@$DOMAIN' WHERE username='$u' AND NOT EXISTS (SELECT 1 FROM (SELECT username FROM users) x WHERE x.username='$u@$DOMAIN');
"
done
for u in $LOCK_USERS; do
  h=$(rnd | hash)
  sql+="UPDATE users SET passwd='$h' WHERE username='$u@$DOMAIN'; DELETE FROM sessions WHERE userid=(SELECT userid FROM users WHERE username='$u@$DOMAIN');
"
done
# O restore da producao traz o akadmin ligado ao diretorio SAML antigo, e o Zabbix 7.0 trata
# userdirectoryid != NULL como externo e recusa a senha local, mesmo com hash certo. Isso precisa
# valer SEMPRE, inclusive sem arquivo de senha: sem esta linha o akadmin volta quebrado depois de
# cada restore (aconteceu em 10/11).
sql+="UPDATE users SET userdirectoryid=NULL WHERE username='akadmin'; DELETE FROM sessions WHERE userid=(SELECT userid FROM users WHERE username='akadmin');"

if [[ -n ${AKADMIN_PASS_FILE:-} ]]; then
  [[ -f $AKADMIN_PASS_FILE ]] || { echo "sem $AKADMIN_PASS_FILE" >&2; exit 2; }
  h=$(hash <"$AKADMIN_PASS_FILE")
  sql+="UPDATE users SET passwd='$h' WHERE username='akadmin';"
fi
((apply)) || { echo "$sql" | sed -E "s/passwd='[^']*'/passwd='<hash>'/"; echo "(simulacao; use --apply)"; exit 0; }

mkdir -p "$BACKUP"; chmod 700 "$BACKUP"
echo "SELECT * FROM userdirectory; SELECT * FROM userdirectory_saml; SELECT userid,username,passwd FROM users;" | $MYSQL >"$BACKUP/antes.tsv"
chmod 600 "$BACKUP/antes.tsv"
[[ -f $CERT_DST ]] && cp -p "$CERT_DST" "$BACKUP/idp.crt"
install -m 640 -g "${ZBX_WEB_GROUP:-www-data}" "$CERT_SRC" "$CERT_DST"
echo "$sql" | $MYSQL
# shellcheck disable=SC2016  # $SSO[ e texto literal de PHP
grep -qF '$SSO[' "$WEBCONF" || echo "\$SSO['SETTINGS'] = ['use_proxy_headers' => true];" >>"$WEBCONF"
echo "OK: SAML Entra aplicado (backup $BACKUP)"
