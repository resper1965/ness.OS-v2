"""Wazuh integratord -> Hub (POST /api/secops/ingest/wazuh).

Called by wazuh-integratord as: custom-ness-hub.py <alert_file> <api_key> <hook_url>.
The alert has no agent group; it comes from wazuh-db, because the Hub resolves the
customer only by group. Vulnerability alerts are skipped: they reach the Hub through
the monthly load (vuln-carga.sh), not as SOC alerts.
"""

import json
import socket
import struct
import sys
import urllib.request

WDB = "/var/ossec/queue/db/wdb"


def agent_groups(agent_id: str) -> list[str]:
    """Groups from wazuh-db; empty on any failure (the Hub then marks it pending)."""
    try:
        with socket.socket(socket.AF_UNIX) as s:
            s.settimeout(5)
            s.connect(WDB)
            msg = f"global get-agent-info {int(agent_id)}".encode()
            s.sendall(struct.pack("<I", len(msg)) + msg)
            size = struct.unpack("<I", s.recv(4))[0]
            data = b""
            while len(data) < size:
                data += s.recv(size - len(data))
        status, _, body = data.decode().partition(" ")
        group = json.loads(body)[0].get("group") if status == "ok" else None
        return [g for g in (group or "").split(",") if g]
    except (OSError, ValueError, IndexError, struct.error):
        return []


def prepare(alert: dict) -> dict | None:
    """Alert ready to send, or None when it must not go to the SOC queue."""
    if "vulnerability-detector" in (alert.get("rule") or {}).get("groups", []):
        return None
    agent = alert.setdefault("agent", {})
    if "group" not in agent and str(agent.get("id", "000")) != "000":
        agent["group"] = agent_groups(str(agent["id"]))
    return alert


def main(alert_file: str, api_key: str, url: str) -> int:
    with open(alert_file, encoding="utf-8", errors="replace") as f:
        alert = prepare(json.load(f))
    if alert is None:
        return 0
    req = urllib.request.Request(
        url,
        data=json.dumps(alert).encode(),
        headers={"Content-Type": "application/json", "X-Api-Key": api_key},
    )
    # ponytail: no retry/queue; a failed POST is logged in integrations.log and the
    # alert stays in alerts.json and the indexer. Add a spool if failures show up.
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()
    except OSError as exc:
        print(
            f"custom-ness-hub: falha ao enviar {alert.get('id')}: {exc}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
