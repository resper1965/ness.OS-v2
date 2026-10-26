#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ ${EUID} == 0 ]] || { echo 'root required' >&2; exit 2; }
source_root="${1:?path to staged repository required}"
readonly frontend=/usr/share/zabbix
readonly stamp="$(date +%Y%m%dT%H%M%S%z)"
readonly rollback="/var/lib/ness-os/restore-evidence/branding-${stamp}"
[[ -f ${frontend}/include/classes/helpers/CBrandHelper.php ]]
grep -Fq 'local/conf/brand.conf.php' "${frontend}/include/classes/helpers/CBrandHelper.php"
php -l "${source_root}/infra/zabbix/brand.conf.php" >/dev/null
for asset in logo_login_black.png logo_menu_white.png logo_menu_rec_white.png; do
  [[ -f ${source_root}/ness_logos/${asset} ]]
done
install -d -m 0700 "${rollback}"
if [[ -f ${frontend}/local/conf/brand.conf.php ]]; then
  cp -a "${frontend}/local/conf/brand.conf.php" "${rollback}/brand.conf.php"
else
  touch "${rollback}/CONFIG_WAS_ABSENT"
fi
if [[ -d ${frontend}/assets/img/ness ]]; then
  cp -a "${frontend}/assets/img/ness" "${rollback}/assets"
else
  touch "${rollback}/ASSETS_WERE_ABSENT"
fi
install -d -m 0755 "${frontend}/local/conf" "${frontend}/assets/img/ness"
for asset in logo_login_black.png logo_menu_white.png logo_menu_rec_white.png; do
  install -m 0644 "${source_root}/ness_logos/${asset}" "${frontend}/assets/img/ness/${asset}"
  cmp "${source_root}/ness_logos/${asset}" "${frontend}/assets/img/ness/${asset}"
done
install -m 0644 "${source_root}/infra/zabbix/brand.conf.php" "${frontend}/local/conf/brand.conf.php"
php -l "${frontend}/local/conf/brand.conf.php" >/dev/null
printf 'native_branding=PASS rollback=%s\n' "${rollback}"
