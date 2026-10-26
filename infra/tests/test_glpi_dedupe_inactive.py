import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "glpi_dedupe_inactive.py"
spec = importlib.util.spec_from_file_location("glpi_dedupe_inactive", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def account(user_id, name, active, auth_type):
    return {"id": user_id, "name": name, "is_active": active, "authtype": auth_type}


def test_only_inactive_legacy_can_be_renamed():
    old = account(8, "same-login", 0, 1)
    canonical = account(93, "same-login", 1, 3)
    assert module.plan_inactive_pair(old, canonical, {"same-login"}) == "ness-legacy-inactive-8-20261013"


@pytest.mark.parametrize(
    "old,canonical,names",
    [
        (account(8, "same-login", 1, 1), account(93, "same-login", 1, 3), set()),
        (account(8, "same-login", 0, 1), account(93, "other", 1, 3), set()),
        (account(8, "same-login", 0, 1), account(93, "same-login", 1, 1), set()),
        (account(8, "same-login", 0, 1), account(93, "same-login", 1, 3), {"ness-legacy-inactive-8-20261013"}),
    ],
)
def test_ambiguous_pair_is_rejected(old, canonical, names):
    with pytest.raises(ValueError):
        module.plan_inactive_pair(old, canonical, names)
