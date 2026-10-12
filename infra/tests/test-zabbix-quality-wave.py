import importlib.util
import ast
from copy import deepcopy
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "quality_wave",
    Path(__file__).resolve().parents[1] / "scripts/zabbix-quality-wave.py",
)
wave = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wave)


def test_unconfigured_waves_cover_only_the_confirmed_zero_item_hosts():
    script = Path(__file__).resolve().parents[1] / 'scripts/tag-zabbix-uat-unconfigured.py'
    tree = ast.parse(script.read_text())
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'hostids' for t in n.targets))
    waves = ast.literal_eval(assignment.value.value)
    ids = [hostid for group in waves.values() for hostid in group]
    assert len(ids) == len(set(ids)) == 14
    assert all(1 <= len(group) <= 5 for group in waves.values())
    assert set(ids) == {str(i) for i in range(10740, 10752)} | {'10791', '10962'}
    assert '10978' not in ids  # Synthetic trapper host is intentionally excluded.


def host():
    return {
        "hostid": "1",
        "tags": [{"tag": "legacy", "value": "keep"}],
        "parentTemplates": [{"templateid": "10", "name": "Linux"}],
    }


def test_plan_preserves_unrelated_tags_and_template_history():
    plan = wave.make_plan(
        [host()], [{"hostid": "1", "tags": {"tenant": "ness"}, "templates": ["20"]}]
    )
    assert plan[0]["after"]["tags"] == [
        {"tag": "legacy", "value": "keep"},
        {"tag": "tenant", "value": "ness"},
    ]
    assert plan[0]["after"]["templates"] == [{"templateid": "20"}]
    assert "templates_clear" not in str(plan)


def test_batch_limit_and_missing_host_fail_closed():
    with pytest.raises(ValueError):
        wave.make_plan([host()], [{"hostid": str(i), "tags": {}} for i in range(6)])
    with pytest.raises(ValueError):
        wave.make_plan([host()], [{"hostid": "missing", "tags": {}}])


def test_rejects_destructive_or_unexpected_fields():
    for field in ("templates_clear", "status", "interfaces"):
        with pytest.raises(ValueError):
            wave.make_plan([host()], [{"hostid": "1", field: []}])


class Api:
    def __init__(self):
        self.state = {"1": wave.normalize(host())}
        self.writes = []

    def get(self, hostids):
        return [deepcopy(self.state[i]) for i in hostids]

    def update(self, payload):
        self.writes.append(deepcopy(payload))
        self.state[payload["hostid"]] = deepcopy(payload)


def test_apply_is_idempotent_and_rollback_restores_snapshot():
    api = Api()
    plan = wave.make_plan([host()], [{"hostid": "1", "tags": {"tenant": "ness"}}])
    wave.apply_plan(api, plan)
    wave.apply_plan(api, plan)
    assert len(api.writes) == 1
    wave.apply_plan(api, plan, rollback=True)
    assert api.state["1"] == wave.normalize(host())


def test_drift_aborts_before_first_write():
    api = Api()
    plan = wave.make_plan([host()], [{"hostid": "1", "tags": {"tenant": "ness"}}])
    api.state["1"]["tags"].append({"tag": "other", "value": "operator-edit"})
    with pytest.raises(ValueError):
        wave.apply_plan(api, plan)
    assert api.writes == []
