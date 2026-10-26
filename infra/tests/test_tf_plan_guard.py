import json
import subprocess
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "tf-plan-guard.sh"


def run_guard(tmp_path, plan):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(plan))
    return subprocess.run(["bash", str(GUARD), str(f)], capture_output=True, text=True)


def change(*actions):
    return {"format_version": "1.2", "resource_changes": [{"address": 'contabo_instance.vps["aiops"]', "change": {"actions": list(actions)}}]}


def test_guard_rejects_replace(tmp_path):
    assert run_guard(tmp_path, change("delete", "create")).returncode == 1


def test_guard_rejects_delete(tmp_path):
    assert run_guard(tmp_path, change("delete")).returncode == 1


def test_guard_accepts_noop(tmp_path):
    assert run_guard(tmp_path, change("no-op")).returncode == 0


def test_guard_accepts_empty_plan(tmp_path):
    assert run_guard(tmp_path, {"format_version": "1.2"}).returncode == 0

def test_guard_rejects_create_before_destroy(tmp_path):
    assert run_guard(tmp_path, change("create", "delete")).returncode == 1

def test_guard_rejects_forget(tmp_path):
    assert run_guard(tmp_path, change("forget")).returncode == 1

def test_guard_rejects_non_plan_and_garbage(tmp_path):
    assert run_guard(tmp_path, {}).returncode == 1
    (tmp_path / "bad.json").write_text("{nope")
    r = subprocess.run(["bash", str(GUARD), str(tmp_path / "bad.json")], capture_output=True, text=True)
    assert r.returncode == 1 and "unreadable" in r.stderr
    assert subprocess.run(["bash", str(GUARD), str(tmp_path / "missing.json")]).returncode == 1

def test_guard_reads_stdin():
    r = subprocess.run(["bash", str(GUARD), "-"], input=json.dumps(change("delete")), capture_output=True, text=True)
    assert r.returncode == 1
