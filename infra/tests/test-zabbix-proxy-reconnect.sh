#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="${repo_root}/infra/scripts/monitor-zabbix-proxy-reconnect.sh"
tmp="$(mktemp -d)"
trap 'rm -rf -- "${tmp}"' EXIT
mkdir -p "${tmp}/bin"
export PATH="${tmp}/bin:${PATH}" SQL_OUT="${tmp}/query.sql"
# ssh stub: saves the SQL sent; answers N/N only if the query keeps the LEFT JOIN, COUNT(*) and the exclusion; else a mismatch
cat >"${tmp}/bin/ssh" <<'F'
#!/usr/bin/env bash
cmd="${!#}"
sed -n 's/.* -e "\(.*\)"$/\1/p' <<<"${cmd}" >"${SQL_OUT}"
if [[ "${cmd}" == *"COUNT(*)"* && "${cmd}" == *"LEFT JOIN proxy_rtdata"* && "${cmd}" == *"WHERE p.name <> 'stacavprx';"* ]]; then
  echo "${STUB_OUT:-18/18}"
else
  echo 18/19
fi
F
chmod +x "${tmp}/bin/ssh"

bash -n "${script}"

# 18/18 after exclusion -> success
TIMEOUT_SECONDS=5 timeout 60 bash "${script}" >/dev/null
# criterion is fresh==total, not a fixed 18
STUB_OUT=5/5 TIMEOUT_SECONDS=5 timeout 60 bash "${script}" >/dev/null
# 0/0 must not count as success
rc=0; STUB_OUT=0/0 TIMEOUT_SECONDS=1 timeout 3 bash "${script}" >/dev/null 2>&1 || rc=$?
[[ ${rc} != 0 ]]
# invalid RETIRED_PROXY is rejected (no injection into the remote SQL)
rc=0; RETIRED_PROXY="x' OR '1'='1" timeout 60 bash "${script}" >/dev/null 2>&1 || rc=$?
[[ ${rc} == 2 ]]

# semantics: run the exact query the script sent against sqlite
timeout 60 python3 - "$(cat "${SQL_OUT}")" <<'P'
import sqlite3, sys, time
db = sqlite3.connect(":memory:")
db.create_function("UNIX_TIMESTAMP", 0, lambda: int(time.time()))
db.create_function("CONCAT", -1, lambda *a: "".join(map(str, a)))
db.executescript("""
CREATE TABLE proxy(proxyid, name); CREATE TABLE proxy_rtdata(proxyid, lastaccess);
INSERT INTO proxy VALUES (1,'fresh'),(2,'novo-sem-rtdata'),(3,'stacavprx');
INSERT INTO proxy_rtdata VALUES (3,0);
""")
db.execute("INSERT INTO proxy_rtdata VALUES (1,?)", (int(time.time()),))
got = db.execute(sys.argv[1]).fetchone()[0]
assert got == "1/2", got
P
echo ok
