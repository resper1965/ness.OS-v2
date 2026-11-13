from datetime import datetime, timezone

from app.api.routers.contabo import build_overview

NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)


def _raw(**over):
    raw = {
        "instances": [
            {
                "instanceId": 1,
                "displayName": "aiops",
                "status": "running",
                "cpuCores": 8,
                "ramMb": 24576,
                "diskMb": 409600,
                "regionName": "European Union",
                "ipConfig": {"v4": {"ip": "10.0.0.1"}},
            },
            {
                "instanceId": 2,
                "displayName": "zbx",
                "status": "stopped",
                "cpuCores": 4,
                "ramMb": 8192,
                "diskMb": 204800,
                "cancelDate": "2026-12-01",
                "errorMessage": "",
            },
            {"instanceId": 3, "displayName": "old", "status": "uninstalled"},
        ],
        "firewalls": [
            {"firewallId": "fw", "name": "borda", "instances": [{"instanceId": 1}]}
        ],
        "networks": [],
        "snapshots": {1: [{"createdDate": "2026-11-12T00:00:00Z"}], 2: []},
        "storages": [
            {
                "objectStorageId": "s1",
                "displayName": "backup",
                "totalPurchasedSpaceTB": 1,
            }
        ],
        "storage_stats": {"s1": {"usedSpaceTB": 0.9, "usedSpacePercentage": 90.0}},
        "audits": {
            "instância": [
                {
                    "timestamp": "2026-11-12T10:00:00Z",
                    "instanceId": 2,
                    "action": "UPDATED",
                    "username": "x@ness.com.br",
                    "changes": {"status": {}},
                }
            ],
            "firewall": [],
            "snapshot": [],
        },
    }
    raw.update(over)
    return raw


def test_overview_totals_skip_uninstalled():
    fleet = build_overview(_raw(), NOW)["fleet"]
    assert fleet["instances"] == 2 and fleet["cpu"] == 12 and fleet["ram_gb"] == 32.0
    assert fleet["statuses"] == {"running": 1, "stopped": 1}


def test_overview_risks():
    risks = {(r["kind"], r["target"]) for r in build_overview(_raw(), NOW)["risks"]}
    assert risks == {
        ("cancel", "zbx"),
        ("status", "zbx"),
        ("firewall", "zbx"),
        ("snapshot", "zbx"),
        ("storage", "backup"),
    }
    assert build_overview(_raw(), NOW)["risks"][0]["level"] == "bad"


def test_overview_old_snapshot_and_timeline():
    o = build_overview(
        _raw(snapshots={1: [{"createdDate": "2026-10-01T00:00:00Z"}], 2: []}), NOW
    )
    assert any(r["detail"] == "último snapshot há 43 dias" for r in o["risks"])
    assert o["events"][0] == {
        "at": "2026-11-12T10:00:00Z",
        "kind": "instância",
        "action": "UPDATED",
        "target": "zbx",
        "by": "x@ness.com.br",
        "fields": ["status"],
    }
