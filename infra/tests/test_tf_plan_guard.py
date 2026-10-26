import json
import subprocess
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "tf-plan-guard.sh"


def run_guard(tmp_path, plan):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(plan))
    return subprocess.run(["bash", str(GUARD), str(f)], capture_output=True, text=True)


def change(*actions):
    return {"resource_changes": [{"address": 'contabo_instance.vps["aiops"]', "change": {"actions": list(actions)}}]}


def test_guard_rejects_replace(tmp_path):
    assert run_guard(tmp_path, change("delete", "create")).returncode == 1


def test_guard_rejects_delete(tmp_path):
    assert run_guard(tmp_path, change("delete")).returncode == 1


def test_guard_accepts_noop(tmp_path):
    assert run_guard(tmp_path, change("no-op")).returncode == 0


def test_guard_accepts_empty_plan(tmp_path):
    assert run_guard(tmp_path, {}).returncode == 0
