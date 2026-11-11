#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT="$(cd "$(dirname "$0")/../scripts" && pwd)/zabbix-saml-entra-apply.sh"
S() { bash "$SCRIPT" "$@"; }
d=$(mktemp -d); trap 'rm -rf "$d"' EXIT
openssl req -x509 -newkey rsa:2048 -nodes -keyout "$d/k" -out "$d/c.crt" -days 30 -subj /CN=t 2>/dev/null
printf '#!/bin/sh\ncat >/dev/null; printf "FAKEHASH"\n' >"$d/hash"; chmod +x "$d/hash"
printf 'pw\n' >"$d/pw"; printf '<?php\n' >"$d/web.php"
T=3b1a6aeb-5d84-4bc9-8442-92226a949039
w() { printf 'TENANT_ID=%s\nDOMAIN=ex.com\nSP_ENTITY=https://z.ex.com\nCERT_SRC=%s\nSSO_USERS="%s"\nLOCK_USERS="%s"\nAKADMIN_PASS_FILE=%s\n' "$1" "$d/c.crt" "$2" "$3" "$d/pw" >"$d/cfg"; }
ZBX_WEB_GROUP=$(id -gn)
export ZBX_WEB_GROUP ZBX_SAML_CONFIG="$d/cfg" ZBX_HASH_BIN="$d/hash" ZBX_WEB_CONF="$d/web.php" ZBX_CERT_DST="$d/idp.crt" ZBX_BACKUP_DIR="$d/bk" ZBX_MYSQL="cat"
w "$T" "alice bob" "bob"
S >"$d/dry"; [[ ! -e $d/idp.crt ]] || { echo "simulacao instalou cert" >&2; exit 1; }
grep -q "<hash>" "$d/dry"; grep -q FAKEHASH "$d/dry" && { echo "hash vazou na simulacao" >&2; exit 1; }
S --apply >"$d/out"
[[ -f $d/idp.crt && -f $d/bk/antes.tsv ]]
[[ $(stat -c %a "$d/idp.crt") == 640 && $(stat -c %G "$d/idp.crt") == "$(id -gn)" ]] || { echo "cert sem modo/grupo esperados" >&2; exit 1; }
grep -q "saml_auth_enabled=1" "$d/out"
grep -q "https://sts.windows.net/$T/" "$d/out"
grep -q "SET username='alice@ex.com' WHERE username='alice'" "$d/out"
grep -q "SET passwd='FAKEHASH' WHERE username='bob@ex.com'" "$d/out"
grep -q "passwd='FAKEHASH' WHERE username='alice@ex.com'" "$d/out" && { echo "alice nao devia ser bloqueada" >&2; exit 1; }
grep -q "userdirectoryid=NULL WHERE username='akadmin'" "$d/out"
S --apply >/dev/null; [[ $(grep -c 'SSO\[' "$d/web.php") == 1 ]] || { echo "SSO duplicado" >&2; exit 1; }
w "x" "alice" "alice"; S --apply >/dev/null 2>&1 && { echo "aceitou tenant ruim" >&2; exit 1; }
w "$T" "a'b" "a'b"; S --apply >/dev/null 2>&1 && { echo "aceitou usuario com aspas" >&2; exit 1; }
w "$T" "alice" "bob"; S --apply >/dev/null 2>&1 && { echo "aceitou LOCK fora de SSO" >&2; exit 1; }
# Sem AKADMIN_PASS_FILE o restore deixaria o akadmin preso ao diretorio SAML antigo e recusando
# senha local (aconteceu em 10/11). O desligamento do diretorio tem de ocorrer de qualquer forma.
printf 'TENANT_ID=%s\nDOMAIN=ex.com\nSP_ENTITY=https://z.ex.com\nCERT_SRC=%s\nSSO_USERS="alice"\nLOCK_USERS=""\n' "$T" "$d/c.crt" >"$d/noak.conf"
ZBX_SAML_CONFIG="$d/noak.conf" S >"$d/noak.out" || { echo "falhou sem AKADMIN_PASS_FILE" >&2; exit 1; }
grep -q "userdirectoryid=NULL WHERE username='akadmin'" "$d/noak.out" || { echo "sem AKADMIN_PASS_FILE, akadmin ficaria preso ao diretorio" >&2; exit 1; }
grep -q "SET passwd='FAKEHASH' WHERE username='akadmin'" "$d/noak.out" && { echo "trocou senha do akadmin sem arquivo" >&2; exit 1; }
echo PASS
