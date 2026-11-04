import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "bf", Path(__file__).parents[1] / "scripts/hub-zabbix-backfill.py"
)
bf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bf)


def test_split_events_separates_recovered_from_open():
    events = [
        {"eventid": "1", "r_eventid": "9"},
        {"eventid": "2", "r_eventid": "0"},
        {"eventid": "3", "r_eventid": None},
    ]
    done, opened = bf.split_events(events)
    assert done == {"1": "9"} and opened == ["2", "3"]
