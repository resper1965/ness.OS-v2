"""ufw_stale.py: only `wazuh-r3a:` rules whose comment left the desired set are deleted, highest number first."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "ufw_stale", Path(__file__).parents[1] / "ansible/roles/wazuh/files/ufw_stale.py")
ufw_stale = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ufw_stale)

STATUS = """Status: active

     To                         Action      From
     --                         ------      ----
[ 1] 2222/tcp                   ALLOW IN    Anywhere                   # SSH - porta customizada
[ 2] 443/tcp                    ALLOW IN    100.64.0.0/10              # wazuh-r3a:admin:443:100.64.0.0/10
[ 3] 55000/tcp                  ALLOW IN    100.64.0.0/10              # wazuh-r3a:admin:55000:100.64.0.0/10
[ 4] 1514/tcp                   ALLOW IN    10.0.0.0/8                 # wazuh-r3a:agent:1514:10.0.0.0/8
[ 5] 1515/tcp                   ALLOW IN    10.0.0.0/8                 # wazuh-r3a:agent:1515:10.0.0.0/8
[ 6] 1514/tcp                   ALLOW IN    203.0.113.0/24             # wazuh-r3a:agent:1514:203.0.113.0/24
[ 7] 443/tcp                    ALLOW IN    Anywhere                   # Zabbix HTTPS
[ 8] 1514/tcp (v6)              ALLOW IN    Anywhere (v6)              # wazuh-r3a:agent:1514:any
[ 9] 8080/tcp                   ALLOW IN    Anywhere
"""
DESIRED = {
    "wazuh-r3a:admin:443:100.64.0.0/10", "wazuh-r3a:admin:55000:100.64.0.0/10",
    "wazuh-r3a:agent:1514:10.0.0.0/8", "wazuh-r3a:agent:1515:10.0.0.0/8",
}

# 203.0.113.0/24 and the `any` source left the list; SSH, Zabbix and the uncommented rule stay.
assert ufw_stale.stale(STATUS, DESIRED) == [8, 6]
# Nothing differs -> nothing to delete (idempotent).
assert ufw_stale.stale(STATUS, DESIRED | {"wazuh-r3a:agent:1514:203.0.113.0/24", "wazuh-r3a:agent:1514:any"}) == []
# Shrinking the tailnet rule set is also reconciled.
assert ufw_stale.stale(STATUS, DESIRED - {"wazuh-r3a:admin:443:100.64.0.0/10"} | {"wazuh-r3a:agent:1514:203.0.113.0/24", "wazuh-r3a:agent:1514:any"}) == [2]
print("ok")
