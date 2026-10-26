"""Reconcile one proven inactive GLPI login collision via the native REST API."""

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


LEGACY_ID = 8
CANONICAL_ID = 93
SNAPSHOT = Path("/opt/n-infraops/rollback/glpi-dedupe-20261013/user8-before.json")


def plan_inactive_pair(old, canonical, existing_names):
    if (
        int(old["id"]) != LEGACY_ID
        or int(canonical["id"]) != CANONICAL_ID
        or int(old["is_active"]) != 0
        or int(canonical["is_active"]) != 1
        or int(old["authtype"]) not in (0, 1)
        or int(canonical["authtype"]) != 3
        or not str(old["name"]).strip()
        or str(old["name"]).casefold() != str(canonical["name"]).casefold()
    ):
        raise ValueError("pair is not the expected inactive legacy / active LDAP collision")
    target = f"ness-legacy-inactive-{LEGACY_ID}-20261013"
    if target.casefold() in {str(name).casefold() for name in existing_names}:
        raise ValueError("target login already exists")
    return target


def api_request(base, path, headers, method="GET", body=None):
    payload = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        f"{base}/{path}", data=payload,
        headers={**headers, "Content-Type": "application/json"}, method=method,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def runtime_credentials():
    if os.geteuid() != 0:
        raise PermissionError("run as root on the GLPI host")
    token = Path("/etc/ness-os/glpi-maintenance.token").read_text().strip()
    if not token:
        raise RuntimeError("administrative token missing")
    container = json.loads(subprocess.check_output(["docker", "inspect", "ninf-api"]))[0]
    env = dict(entry.split("=", 1) for entry in container["Config"]["Env"] if "=" in entry)
    app_token = env["NINF_GLPI_APP_TOKEN"]
    glpi = json.loads(subprocess.check_output(["docker", "inspect", "ninf-glpi"]))[0]
    address = glpi["NetworkSettings"]["Networks"]["app_ninf-net"]["IPAddress"]
    if not address or not app_token:
        raise RuntimeError("GLPI endpoint or App-Token missing")
    return f"http://{address}/apirest.php", token, app_token


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    base, token, app_token = runtime_credentials()
    session = api_request(
        base, "initSession", {"Authorization": f"user_token {token}", "App-Token": app_token}
    )["session_token"]
    headers = {"Session-Token": session, "App-Token": app_token}
    try:
        old = api_request(base, f"User/{LEGACY_ID}", headers)
        canonical = api_request(base, f"User/{CANONICAL_ID}", headers)
        users = api_request(base, "User?range=0-999", headers)
        if not isinstance(users, list) or len(users) < 2:
            raise RuntimeError("user listing incomplete")
        target = plan_inactive_pair(old, canonical, {user["name"] for user in users})
        if not args.apply:
            print(json.dumps({"mode": "dry-run", "legacy_id": LEGACY_ID, "canonical_id": CANONICAL_ID, "ready": True}))
            return
        SNAPSHOT.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        SNAPSHOT.parent.chmod(0o700)
        fd = os.open(SNAPSHOT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump({"legacy": old, "canonical": canonical}, out)
        updated = False
        try:
            result = api_request(base, f"User/{LEGACY_ID}", headers, "PUT", {"input": {"name": target, "is_active": 0}})
            if not isinstance(result, list) or not result or result[0].get(str(LEGACY_ID)) is not True:
                raise RuntimeError("GLPI rejected user update")
            updated = True
            after = api_request(base, f"User/{LEGACY_ID}", headers)
            kept = api_request(base, f"User/{CANONICAL_ID}", headers)
            if after["name"] != target or int(after["is_active"]) != 0 or kept["name"] != canonical["name"] or int(kept["is_active"]) != 1:
                raise RuntimeError("readback mismatch")
        except Exception:
            if updated:
                api_request(base, f"User/{LEGACY_ID}", headers, "PUT", {"input": {"name": old["name"], "is_active": old["is_active"]}})
            raise
        print(json.dumps({"mode": "applied", "legacy_id": LEGACY_ID, "canonical_id": CANONICAL_ID, "readback": "pass"}))
    finally:
        api_request(base, "killSession", headers)


if __name__ == "__main__":
    main()
