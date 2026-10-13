#!/usr/bin/env python3
"""Read-only diagnostic, not an approval of GLPI API entity isolation."""

import json
import subprocess


def assess_networks(api: set[str], glpi: set[str]) -> dict[str, object]:
    if not api or not glpi:
        status = "UNKNOWN_NETWORK_TOPOLOGY"
    elif api & glpi:
        status = "BLOCKED_DIRECT_PATH"
    else:
        status = "NETWORK_SEPARATED_UNVERIFIED"
    return {"status": status, "shared_networks": len(api & glpi)}


def main() -> int:
    # The format excludes container environment, mounts and other secret-bearing
    # inspect fields. Never print the raw response or Docker's error output.
    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{json .NetworkSettings.Networks}}",
                "ninf-api",
                "ninf-glpi",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        lines = result.stdout.splitlines()
        if len(lines) != 2:
            raise ValueError("unexpected container count")
        networks = [json.loads(line) for line in lines]
        if any(not isinstance(item, dict) for item in networks):
            raise ValueError("invalid network topology")
        report = assess_networks(set(networks[0]), set(networks[1]))
    except (OSError, ValueError, subprocess.SubprocessError):
        report = assess_networks(set(), set())

    print(json.dumps(report, sort_keys=True))
    # Even separate Docker networks do not prove that Caddy/public routes,
    # credential distribution and API paths are isolated.
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
