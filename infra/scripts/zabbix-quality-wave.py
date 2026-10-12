#!/usr/bin/env python3
"""Plan five-host quality waves; apply only to the approved isolated UAT API."""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import urllib.request


def normalize(host):
    templates = host.get("templates", host.get("parentTemplates", []))
    return {
        "hostid": str(host["hostid"]),
        "tags": sorted(
            [{"tag": t["tag"], "value": t["value"]} for t in host.get("tags", [])],
            key=lambda t: (t["tag"], t["value"]),
        ),
        "templates": sorted(
            [{"templateid": str(t["templateid"])} for t in templates],
            key=lambda t: t["templateid"],
        ),
    }


def make_plan(hosts, desired):
    if not 1 <= len(desired) <= 5:
        raise ValueError("wave requires one to five hosts")
    inventory = {str(h["hostid"]): h for h in hosts}
    plan, seen = [], set()
    for change in desired:
        if set(change) - {"hostid", "tags", "templates"}:
            raise ValueError("only tags and linked templates may change")
        hostid = str(change["hostid"])
        if hostid in seen or hostid not in inventory:
            raise ValueError("duplicate or missing host")
        seen.add(hostid)
        before = normalize(inventory[hostid])
        after = deepcopy(before)
        tags = change.get("tags", {})
        if not isinstance(tags, dict) or any(
            not isinstance(k, str) or not k or not isinstance(v, str) or not v
            for k, v in tags.items()
        ):
            raise ValueError("tags require nonempty names and confirmed values")
        after["tags"] = [t for t in before["tags"] if t["tag"] not in tags]
        after["tags"] += [{"tag": k, "value": v} for k, v in tags.items()]
        if "templates" in change:
            if not change["templates"] or len(set(change["templates"])) != len(
                change["templates"]
            ):
                raise ValueError("explicit template set must be nonempty and unique")
            after["templates"] = [{"templateid": str(t)} for t in change["templates"]]
        plan.append({"before": before, "after": normalize(after)})
    return plan


def apply_plan(api, plan, rollback=False):
    if not 1 <= len(plan) <= 5:
        raise ValueError("wave requires one to five hosts")
    expected_key, target_key = ("after", "before") if rollback else ("before", "after")
    for row in plan:
        for side in ("before", "after"):
            if set(row[side]) != {"hostid", "tags", "templates"}:
                raise ValueError("invalid snapshot fields")
        if row["before"]["hostid"] != row["after"]["hostid"]:
            raise ValueError("host identity cannot change")
    ids = [row["before"]["hostid"] for row in plan]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate host")
    current = {h["hostid"]: normalize(h) for h in api.get(ids)}
    for row in plan:
        if current.get(row["before"]["hostid"]) not in (
            row[expected_key],
            row[target_key],
        ):
            raise ValueError("precondition drift; no writes performed")
    for row in plan:
        hostid = row["before"]["hostid"]
        if normalize(api.get([hostid])[0]) == row[target_key]:
            continue
        if normalize(api.get([hostid])[0]) != row[expected_key]:
            raise ValueError("concurrent edit; stop and reconcile completed hosts")
        api.update(row[target_key])
        if normalize(api.get([hostid])[0]) != row[target_key]:
            raise ValueError("update verification failed")


class Api:
    def __init__(self):
        self.url = os.environ["ZABBIX_URL"]
        if self.url != "https://zabbix-uat.ness.com.br/zabbix/api_jsonrpc.php":
            raise ValueError("apply is restricted to isolated UAT")
        self.token = os.environ["ZABBIX_TOKEN"]

    def call(self, method, params):
        request = urllib.request.Request(
            self.url,
            data=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
        if "error" in data:
            raise RuntimeError(
                "Zabbix API rejected request; review permissions and payload"
            )
        return data["result"]

    def get(self, hostids):
        return self.call(
            "host.get",
            {
                "hostids": hostids,
                "output": ["hostid"],
                "selectTags": ["tag", "value"],
                "selectParentTemplates": ["templateid"],
            },
        )

    def update(self, payload):
        return self.call("host.update", payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--desired", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    if args.apply:
        if not args.plan or args.inventory or args.desired:
            parser.error("apply requires only an existing --plan")
        apply_plan(Api(), json.loads(args.plan.read_text()), args.rollback)
        print("quality_wave=PASS")
    else:
        if not args.inventory or not args.desired or args.plan or args.rollback:
            parser.error("dry-run requires --inventory and --desired")
        print(
            json.dumps(
                make_plan(
                    json.loads(args.inventory.read_text()),
                    json.loads(args.desired.read_text()),
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
