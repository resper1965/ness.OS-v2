#!/usr/bin/env python3
"""Fail closed before recreating GLPI if its persistent state volume would change.

Read-only: inspects the resolved Compose model and the running container. It does
not migrate the current anonymous volume; that requires a separate change.
"""

import argparse
import json
import subprocess
import sys


STATE_PATH = "/var/glpi"


def validate_state_volume(compose: dict, inspect: list) -> str:
    services = compose.get("services", {})
    glpi = services.get("glpi", {})
    declared = [v for v in glpi.get("volumes", []) if v.get("target") == STATE_PATH]
    if len(declared) != 1:
        raise ValueError("Compose must declare exactly one /var/glpi mount")
    mount = declared[0]
    source = mount.get("source")
    if mount.get("type") != "volume" or not source:
        raise ValueError("Compose /var/glpi must use a named volume")
    volume = compose.get("volumes", {}).get(source)
    if not isinstance(volume, dict) or not volume.get("name"):
        raise ValueError("Compose /var/glpi named volume must resolve to an explicit name")
    expected = volume["name"]

    if len(inspect) != 1:
        raise ValueError("exactly one running GLPI container is required")
    running = [v for v in inspect[0].get("Mounts", []) if v.get("Destination") == STATE_PATH]
    if len(running) != 1 or running[0].get("Type") != "volume":
        raise ValueError("running GLPI has no unique /var/glpi volume")
    if running[0].get("Name") != expected:
        raise ValueError("Compose /var/glpi volume does not match running GLPI")
    return expected


def _json_command(args: list[str]):
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose", action="append", required=True, help="Compose file, in merge order")
    parser.add_argument("--container", default="ninf-glpi")
    args = parser.parse_args()
    compose_args = [value for path in args.compose for value in ("-f", path)]
    try:
        compose = _json_command(["docker", "compose", *compose_args, "config", "--format", "json"])
        inspect = _json_command(["docker", "inspect", args.container])
        validate_state_volume(compose, inspect)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as exc:
        # Never echo Docker output: resolved Compose may contain credentials.
        reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print(f"GLPI state-volume preflight BLOCKED: {reason}", file=sys.stderr)
        return 1
    print("GLPI state-volume preflight PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
