#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source_script="${repo_root}/infra/scripts/zabbix-cutover-backup.sh"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "${tmpdir}"' EXIT

bash -n "${source_script}"

fake_bin="${tmpdir}/bin"
fake_root="${tmpdir}/root"
test_backup="${tmpdir}/backup/cutover"
mkdir -p "${fake_bin}" "${fake_root}/etc/zabbix" "${fake_root}/etc/apache2" \
  "${fake_root}/etc/mysql" "${fake_root}/etc/letsencrypt"
secret="fixture-$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"
printf 'DBUser=zbx\nDBPassword=%s\nDBName=dbzabbix\n' "${secret}" >"${tmpdir}/zabbix_server.conf"
printf 'fixture\n' >"${fake_root}/etc/zabbix/zabbix_server.conf"

# Run the real script with only paths/privileges redirected to the sandbox.
sed \
  -e "s|readonly backup_root=.*|readonly backup_root=\"${test_backup}\"|" \
  -e "s|readonly zabbix_config=.*|readonly zabbix_config=\"${tmpdir}/zabbix_server.conf\"|" \
  -e "s|readonly lock_file=.*|readonly lock_file=\"${tmpdir}/backup.lock\"|" \
  -e "s|/var/backups/zabbix/cutover/\*)|${test_backup}/*)|" \
  -e 's/install -d -o root -g root -m 700/install -d -m 700/' \
  -e "s|tar -C / |tar -C ${fake_root} |" \
  -e 's/\${EUID} -ne 0/0 -ne 0/' \
  "${source_script}" >"${tmpdir}/script.sh"

cat >"${fake_bin}/flock" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
cat >"${fake_bin}/df" <<'STUB'
#!/usr/bin/env bash
printf 'Avail\n999999999\n'
STUB
cat >"${fake_bin}/systemctl" <<'STUB'
#!/usr/bin/env bash
# is-active [--quiet] unit...  |  show -p ActiveEnterTimestampMonotonic --value zabbix-server
# zabbix-server state/timestamp live in files so the dump stub can change them mid-run.
if [[ "$1" == show ]]; then cat "${ZBX_TEST_STATE}/ts"; exit 0; fi
shift
quiet=0
[[ "${1-}" == --quiet ]] && { quiet=1; shift; }
rc=0
for unit in "$@"; do
  case "${unit}" in
    zabbix-server) state="$(cat "${ZBX_TEST_STATE}/server")" ;;
    mariadb) state="$(cat "${ZBX_TEST_STATE}/mariadb")" ;;
    *) state=active ;;
  esac
  (( quiet )) || printf '%s\n' "${state}"
  [[ "${state}" == active ]] || rc=3
done
exit "${rc}"
STUB
cat >"${fake_bin}/zabbix_server" <<'STUB'
#!/usr/bin/env bash
echo 'zabbix_server (Zabbix) 7.0.27'
STUB
cat >"${fake_bin}/mariadb" <<'STUB'
#!/usr/bin/env bash
printf 'mariadb %s\n' "$*" >>"${ZBX_TEST_ARGV_LOG}"
printf '10.11.18-MariaDB\t7000000\n'
STUB
cat >"${fake_bin}/mariadb-dump" <<'STUB'
#!/usr/bin/env bash
# Credential must come from an option file, never argv; record it for the test.
printf 'mariadb-dump %s\n' "$*" >>"${ZBX_TEST_ARGV_LOG}"
for a in "$@"; do
  if [[ "${a}" == --defaults-extra-file=* ]]; then
    cat "${a#*=}" >"${ZBX_TEST_OPTFILE_COPY}"
    printf '%s\n' "${a#*=}" >"${ZBX_TEST_OPTFILE_PATH}"
  fi
done
printf 'CREATE DATABASE dbzabbix;\n'
[[ "${ZBX_TEST_START_DURING:-0}" == 1 ]] && { echo active >"${ZBX_TEST_STATE}/server"; echo 123 >"${ZBX_TEST_STATE}/ts"; }
# started and stopped again inside the dump: state is back to inactive, timestamp moved
[[ "${ZBX_TEST_BOUNCE_DURING:-0}" == 1 ]] && echo 123 >"${ZBX_TEST_STATE}/ts"
[[ "${ZBX_TEST_TRUNCATED:-0}" == 1 ]] || printf -- '-- Dump completed on 2026-11-09\n'
# fails AFTER a complete-looking stream: only pipefail can catch it
[[ "${ZBX_TEST_DUMP_FAIL:-0}" == 1 ]] && exit 2
exit 0
STUB
cat >"${fake_bin}/nice" <<'STUB'
#!/usr/bin/env bash
shift 2; exec "$@"
STUB
cat >"${fake_bin}/ionice" <<'STUB'
#!/usr/bin/env bash
shift 2; exec "$@"
STUB
chmod +x "${fake_bin}"/*

export PATH="${fake_bin}:${PATH}"
export ZBX_TEST_STATE="${tmpdir}/state" TMPDIR="${tmpdir}/tmp"
mkdir -p "${ZBX_TEST_STATE}" "${TMPDIR}"
reset_state() { echo "${1:-inactive}" >"${ZBX_TEST_STATE}/server"; echo 0 >"${ZBX_TEST_STATE}/ts"; echo active >"${ZBX_TEST_STATE}/mariadb"; }
reset_state
run() { bash "${tmpdir}/script.sh" >"${tmpdir}/out" 2>&1; }
# failed runs must leave no set dir (partial) and no credential file
assert_clean() {
  [[ -z "$(ls -A "${test_backup}")" ]] || { echo "$1: left artifacts" >&2; exit 1; }
  [[ -z "$(ls -A "${TMPDIR}")" ]] || { echo "$1: left temp files" >&2; exit 1; }
}
export ZBX_TEST_ARGV_LOG="${tmpdir}/argv.log" ZBX_TEST_OPTFILE_COPY="${tmpdir}/optfile.copy" \
  ZBX_TEST_OPTFILE_PATH="${tmpdir}/optfile.path"
: >"${ZBX_TEST_ARGV_LOG}"
mkdir -p "${test_backup}"

# (a) refuses while zabbix-server is active or activating, writes nothing
for st in active activating; do
  reset_state "${st}"
  if run; then echo "cutover backup ran with zabbix-server ${st}" >&2; exit 1; fi
  grep -Fq "zabbix-server is ${st}" "${tmpdir}/out"
  assert_clean "server ${st}"
done

# refuses without mariadb
reset_state; echo inactive >"${ZBX_TEST_STATE}/mariadb"
if run; then echo 'cutover backup ran with mariadb inactive' >&2; exit 1; fi
assert_clean 'mariadb inactive'

# server started during the dump (still active, or bounced back to inactive): no COMPLETED
for var in ZBX_TEST_START_DURING ZBX_TEST_BOUNCE_DURING; do
  reset_state
  if env "${var}=1" bash "${tmpdir}/script.sh" >"${tmpdir}/out" 2>&1; then
    echo "${var}: dump accepted although the server was started" >&2; exit 1
  fi
  grep -Fq 'started during the dump' "${tmpdir}/out"
  assert_clean "${var}"
done

# dump command fails (pipefail) / dump truncated: no COMPLETED
for var in ZBX_TEST_DUMP_FAIL ZBX_TEST_TRUNCATED; do
  reset_state
  if env "${var}=1" bash "${tmpdir}/script.sh" >"${tmpdir}/out" 2>&1; then
    echo "${var}: bad dump was accepted" >&2; exit 1
  fi
  assert_clean "${var}"
done

# (b) completes with server stopped: COMPLETED, valid SHA256SUMS, dump readable
reset_state
run || { cat "${tmpdir}/out" >&2; exit 1; }
set_dir="$(cat "${test_backup}/LATEST")"
[[ -f "${set_dir}/COMPLETED" ]]
(cd "${set_dir}" && sha256sum -c SHA256SUMS >/dev/null)
grep -Fq './db/dbzabbix.sql.gz' "${set_dir}/SHA256SUMS"
gzip -t "${set_dir}/db/dbzabbix.sql.gz"
python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); assert m["zabbix_version"]=="7.0.27" and m["db_name"]=="dbzabbix"' \
  "${set_dir}/backup-set-manifest.json"
grep -Fq -- '--single-transaction' "${ZBX_TEST_ARGV_LOG}"
zcat "${set_dir}/db/dbzabbix.sql.gz" | tail -n1 | grep -q '^-- Dump completed' 

# (c) credential never in argv/output/artifacts, option file removed
grep -Fq "${secret}" "${ZBX_TEST_ARGV_LOG}" "${tmpdir}/out" && { echo "secret leaked to argv/output" >&2; exit 1; }
grep -rFq "${secret}" "${set_dir}" && { echo "secret leaked to artifacts" >&2; exit 1; }
grep -Fq "${secret}" "${ZBX_TEST_OPTFILE_COPY}"
[[ ! -e "$(cat "${ZBX_TEST_OPTFILE_PATH}")" ]] || { echo 'credential file left behind' >&2; exit 1; }
[[ -z "$(ls -A "${TMPDIR}")" ]] || { echo 'temp files left behind' >&2; exit 1; }
echo 'zabbix-cutover-backup: ok'
