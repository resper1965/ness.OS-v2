"""Wazuh integratord -> Hub (POST /api/secops/ingest/wazuh).

Called by wazuh-integratord as: custom-ness-hub.py <alert_file> <api_key> <hook_url>.
The alert has no agent group; it comes from wazuh-db, because the Hub resolves the
customer only by group. Vulnerability alerts are skipped: they reach the Hub through
the monthly load (vuln-carga.sh), not as SOC alerts.
"""

import json
import socket
import ssl
import struct
import sys
import urllib.request
from pathlib import Path

WDB = "/var/ossec/queue/db/wdb"
# Wazuh's bundled Python has no CA store: use the OS one (Debian/Ubuntu path).
CA_FILE = "/etc/ssl/certs/ca-certificates.crt"
SPOOL = Path("/var/ossec/logs/ness-hub-spool")


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
    # Triage may wait for threat intel and the model: generous timeout. A failed POST
    # goes to the spool (one file per alert id) and is replayed by the runbook loop;
    # the Hub dedups replays by alert id.
    try:
        with urllib.request.urlopen(
            req, timeout=120, context=ssl.create_default_context(cafile=CA_FILE)
        ) as resp:
            resp.read()
    except OSError as exc:
        SPOOL.mkdir(mode=0o750, exist_ok=True)
        name = str(alert.get("id") or "sem-id").replace("/", "_")
        (SPOOL / f"{name}.json").write_text(json.dumps(alert))
        print(f"custom-ness-hub: falha ao enviar {name}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
