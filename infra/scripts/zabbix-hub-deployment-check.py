"""Exercise only the pre-existing internal deployment-check item on localhost."""

import json
import socket
import struct
import sys

if len(sys.argv) != 3 or sys.argv[1] != "--apply":
    print("Usage: zabbix-hub-deployment-check.py --apply 0|1", file=sys.stderr)
    raise SystemExit(2)

value = sys.argv[2]
if value not in ("0", "1"):
    raise SystemExit("Expected synthetic value 0 or 1")
payload = json.dumps({"request": "sender data", "data": [
    {"host": "uat-synthetic-alerts", "key": "uat.synthetic.alert", "value": value}
]}).encode()
with socket.create_connection(("127.0.0.1", 10051), timeout=10) as connection:
    connection.sendall(b"ZBXD\x01" + struct.pack("<II", len(payload), 0) + payload)
    def receive(size):
        result = b""
        while len(result) < size:
            chunk = connection.recv(size - len(result))
            if not chunk:
                raise RuntimeError("Incomplete Zabbix response")
            result += chunk
        return result
    header = receive(13)
    if header[:5] != b"ZBXD\x01":
        raise RuntimeError("Unexpected Zabbix protocol")
    size = struct.unpack("<II", header[5:])[0]
    if size > 65536:
        raise RuntimeError("Unexpected response size")
    response = json.loads(receive(size))
    print(json.dumps(response))
    if response.get("response") != "success" or "processed: 1; failed: 0" not in response.get("info", ""):
        raise SystemExit(1)
