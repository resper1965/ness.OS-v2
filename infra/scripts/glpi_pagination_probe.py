"""Probe GLPI inventory pagination headers without emitting asset or secret data.

Run as root on the existing GLPI host. This script performs only API reads,
plus the normal temporary session login/logout.
"""

import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path


def _inspect(name):
    return json.loads(subprocess.check_output(["docker", "inspect", name]))[0]


def _request(base, path, headers):
    request = urllib.request.Request(f"{base}/{path}", headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response), response.headers.get("Content-Range")


def _valid_page(page, content_range, offset):
    match = re.fullmatch(r"(?:items\s+)?(\d+)-(\d+)/(\d+)", content_range or "")
    return (
        isinstance(page, list)
        and match is not None
        and int(match.group(1)) == offset
        and int(match.group(2)) == offset
        and len(page) == 1
        and int(match.group(3)) > offset
    )


def main():
    if os.geteuid() != 0:
        raise PermissionError("run as root on the GLPI host")
    token = Path("/etc/ness-os/glpi-maintenance.token").read_text().strip()
    env = dict(
        entry.split("=", 1)
        for entry in _inspect("ninf-api")["Config"]["Env"]
        if "=" in entry
    )
    app_token = env["NINF_GLPI_APP_TOKEN"]
    address = _inspect("ninf-glpi")["NetworkSettings"]["Networks"]["app_ninf-net"][
        "IPAddress"
    ]
    if not token or not app_token or not address:
        raise RuntimeError("GLPI credentials or internal address missing")
    base = f"http://{address}/apirest.php"
    session, _ = _request(
        base,
        "initSession",
        {"Authorization": f"user_token {token}", "App-Token": app_token},
    )
    headers = {"Session-Token": session["session_token"], "App-Token": app_token}
    try:
        for offset in (0, 1):
            page, content_range = _request(
                base, f"Computer?range={offset}-{offset}", headers
            )
            valid = _valid_page(page, content_range, offset)
            print(json.dumps({"offset": offset, "status": "PASS" if valid else "FAIL"}))
            if not valid:
                raise RuntimeError("GLPI inventory pagination contract mismatch")
    finally:
        _request(base, "killSession", headers)


if __name__ == "__main__":
    main()
