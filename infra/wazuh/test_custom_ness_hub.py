"""Run: python3 infra/wazuh/test_custom_ness_hub.py"""

import importlib.util
import json
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "hub", Path(__file__).with_name("custom-ness-hub.py")
)
hub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hub)
hub.agent_groups = lambda agent_id: ["RZK-SOL-ESTACOES", "default"]

assert hub.prepare({"rule": {"groups": ["vulnerability-detector"]}}) is None
a = hub.prepare({"rule": {"groups": ["windows"]}, "agent": {"id": "042"}})
assert a["agent"]["group"] == ["RZK-SOL-ESTACOES", "default"]
assert "group" not in hub.prepare({"rule": {}, "agent": {"id": "000"}})["agent"]
assert hub.prepare({"rule": {}, "agent": {"id": "1", "group": ["g"]}})["agent"][
    "group"
] == ["g"]
print("ok")

hub.SPOOL = Path(tempfile.mkdtemp()) / "spool"
f = hub.SPOOL.parent / "a.json"
f.write_text(json.dumps({"id": "1.2", "rule": {}, "agent": {"id": "000"}}))
assert hub.main(str(f), "k", "http://127.0.0.1:9/") == 1
assert json.loads((hub.SPOOL / "1.2.json").read_text())["id"] == "1.2"
print("spool ok")
