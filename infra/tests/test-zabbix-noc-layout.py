"""Validate the native candidate layout, without calling any production API."""

import json
from pathlib import Path


def test_noc_candidate_is_private_and_has_no_overlapping_widgets():
    payload = json.loads(
        (
            Path(__file__).resolve().parents[2] / "config/zabbix/noc-uat-dashboard.json"
        ).read_text()
    )
    assert payload["private"] == 1
    assert "UAT sem coleta" in payload["name"]
    widgets = payload["pages"][0]["widgets"]
    assert len({w["name"] for w in widgets}) == len(widgets)
    assert {w["type"] for w in widgets} == {
        "systeminfo",
        "hostavail",
        "problemsbysv",
        "problems",
        "problemhosts",
    }
    for index, a in enumerate(widgets):
        assert a["x"] >= 0 and a["y"] >= 0 and a["width"] > 0 and a["height"] > 0
        assert a["x"] + a["width"] <= 72
        for b in widgets[index + 1 :]:
            assert (
                a["x"] + a["width"] <= b["x"]
                or b["x"] + b["width"] <= a["x"]
                or a["y"] + a["height"] <= b["y"]
                or b["y"] + b["height"] <= a["y"]
            )
