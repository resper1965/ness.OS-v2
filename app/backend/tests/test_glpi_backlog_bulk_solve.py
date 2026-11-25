import importlib.util
import pathlib
from datetime import datetime, timedelta, timezone

_p = pathlib.Path(__file__).parents[3] / "infra/scripts/glpi_backlog_bulk_solve.py"
_s = importlib.util.spec_from_file_location("bulk_solve", _p)
mod = importlib.util.module_from_spec(_s)
_s.loader.exec_module(mod)


def test_select_candidates():
    cutoff = datetime(2026, 11, 23, 3, tzinfo=timezone.utc)
    old = {
        "date": cutoff - timedelta(days=1),
        "has_tech": False,
        "has_human_followup": False,
        "hub_state": None,
        "is_noise": False,
    }
    new = {"date": cutoff + timedelta(hours=1)}
    rows = [
        {"id": 1, **old},
        {"id": 2, **old, "has_tech": True},
        {"id": 3, **old, "has_human_followup": True},
        {"id": 4, **old, **new},
        {"id": 5, **old, **new, "hub_state": "panel"},
        {"id": 6, **old, **new, "hub_state": "resolved"},
        {"id": 7, **old, **new, "is_noise": True},
        {"id": 8, **old, **new, "hub_state": "opened"},
    ]
    assert mod.select_candidates(rows, cutoff) == [1, 5, 6, 7]
