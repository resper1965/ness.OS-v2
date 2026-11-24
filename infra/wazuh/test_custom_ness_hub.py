"""Run: python3 infra/wazuh/test_custom_ness_hub.py"""

import importlib.util
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
