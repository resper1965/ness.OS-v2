#!/usr/bin/env python3
"""Probe the local Zabbix frontend status.get path without printing session IDs."""

import json
import socket
import struct
import subprocess
import sys


def active_session() -> str:
    query = (
        "SELECT sessionid FROM sessions "
        "WHERE status=0 AND lastaccess>UNIX_TIMESTAMP()-3600 "
        "ORDER BY lastaccess DESC LIMIT 1;"
    )
    result = subprocess.run(
        ["mysql", "-N", "-B", "dbzabbix", "-e", query],
        check=True,
        capture_output=True,
        text=True,
    )
    sid = result.stdout.strip()
    if not sid:
        raise RuntimeError("no active Zabbix frontend session")
    return sid


def main() -> int:
    payload = json.dumps(
        {"request": "status.get", "type": "ping", "sid": active_session()},
        separators=(",", ":"),
    ).encode()
    frame = b"ZBXD\x01" + struct.pack("<I", len(payload)) + b"\x00\x00\x00\x00" + payload

    with socket.create_connection(("127.0.0.1", 10051), timeout=5) as sock:
        sock.sendall(frame)
        header = sock.recv(13)
        if len(header) != 13 or not header.startswith(b"ZBXD\x01"):
            print("frontend_status_probe=FAIL invalid_or_empty_response")
            return 1
        length = struct.unpack("<I", header[5:9])[0]
        response = b""
        while len(response) < length:
            chunk = sock.recv(length - len(response))
            if not chunk:
                break
            response += chunk

    decoded = json.loads(response.decode())
    decoded.pop("sid", None)
    print("frontend_status_response=" + json.dumps(decoded, sort_keys=True))
    return 0 if decoded.get("response") == "success" else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # concise operational probe output
        print(f"frontend_status_probe=FAIL {type(exc).__name__}: {exc}")
        sys.exit(1)
