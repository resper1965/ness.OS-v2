#!/usr/bin/env python3
"""Validate a staged Zabbix token without printing it."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen


TOKEN = Path("/run/ness-zabbix-hub-readonly/token").read_text().strip()
URL = "https://zabbix.ness.com.br/api_jsonrpc.php"


def call(method: str, params: object, request_id: int, *, authenticated: bool = True):
    headers = {"Content-Type": "application/json-rpc"}
    if authenticated:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = Request(
        URL,
        data=json.dumps(
            {"jsonrpc": "2.0", "method": method, "params": params, "id": request_id}
        ).encode(),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read())


version = call("apiinfo.version", {}, 1, authenticated=False)
hosts = call("host.get", {"output": ["hostid"], "limit": 1}, 2)
denied = call("token.get", {"output": ["tokenid"], "limit": 1}, 3)

if "result" not in version or "result" not in hosts:
    raise SystemExit("read-only token positive probe failed")
if "result" in denied or "error" not in denied:
    raise SystemExit("API allowlist negative probe failed")

print(
    json.dumps(
        {
            "status": "ready",
            "version": version["result"],
            "visible_host_sample_count": len(hosts["result"]),
            "disallowed_method_denied": True,
            "write_operations": 0,
        },
        separators=(",", ":"),
    )
)
