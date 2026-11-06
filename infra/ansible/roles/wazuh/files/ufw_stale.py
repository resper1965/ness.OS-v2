#!/usr/bin/env python3
"""Print the UFW rule numbers (highest first) carrying a `wazuh-r3a:` comment that is not in --desired.

Read-only. Rules without that prefix (SSH, role common, anything manual) are never listed.
Usage: ufw_stale.py --desired '["wazuh-r3a:agent:1514:any", ...]' [--status-file FILE]
"""
import argparse
import json
import re
import subprocess

PREFIX = "wazuh-r3a:"
RULE = re.compile(r"^\[\s*(\d+)\]\s.*#\s*(" + re.escape(PREFIX) + r"\S+)\s*$")


def stale(status: str, desired: set[str]) -> list[int]:
    found = [(int(m[1]), m[2]) for line in status.splitlines() if (m := RULE.match(line))]
    return sorted((n for n, comment in found if comment not in desired), reverse=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--desired", required=True)
    ap.add_argument("--status-file")
    a = ap.parse_args()
    out = open(a.status_file).read() if a.status_file else subprocess.run(
        ["ufw", "status", "numbered"], check=True, capture_output=True, text=True).stdout
    print("\n".join(map(str, stale(out, set(json.loads(a.desired))))))
