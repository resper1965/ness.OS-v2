"""A CI result belongs only to the exact open same-repository PR head."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/local_ci_check_gate.py"
spec = importlib.util.spec_from_file_location("local_ci_check_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
SHA = "a" * 40


def pr():
    return {
        "number": 81,
        "state": "open",
        "head": {
            "sha": SHA,
            "repo": {"id": 100, "full_name": "resper1965/ness.OS-v2"},
        },
        "base": {
            "ref": "main",
            "repo": {"id": 100, "full_name": "resper1965/ness.OS-v2"},
        },
    }


def test_matching_open_pr_head_is_accepted():
    gate.verify_pr_head(pr(), 81, "resper1965/ness.OS-v2", SHA)


@pytest.mark.parametrize(
    "change",
    ["wrong_sha", "closed", "fork", "wrong_base", "wrong_number", "missing_head"],
)
def test_nonmatching_pr_head_is_rejected(change):
    data = pr()
    if change == "wrong_sha":
        data["head"]["sha"] = "b" * 40
    elif change == "closed":
        data["state"] = "closed"
    elif change == "fork":
        data["head"]["repo"] = {"id": 101, "full_name": "other/fork"}
    elif change == "wrong_base":
        data["base"]["ref"] = "develop"
    elif change == "wrong_number":
        data["number"] = 82
    else:
        del data["head"]
    with pytest.raises(ValueError):
        gate.verify_pr_head(data, 81, "resper1965/ness.OS-v2", SHA)
