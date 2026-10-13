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


def assess_consumers(consumers: dict[str, set[str]], glpi: set[str]) -> dict[str, object]:
    direct = sorted(name for name, networks in consumers.items() if networks & glpi)
    shared = set().union(*(networks & glpi for networks in consumers.values()))
    if direct:
        status = "BLOCKED_DIRECT_PATH"
    elif not glpi or not consumers or any(not networks for networks in consumers.values()):
        status = "UNKNOWN_NETWORK_TOPOLOGY"
    else:
        status = "NETWORK_SEPARATED_UNVERIFIED"
    return {"status": status, "shared_networks": len(shared), "direct_consumers": direct}


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
                "ninf-worker-alerts",
                "ninf-glpi",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        lines = result.stdout.splitlines()
        if len(lines) != 3:
            raise ValueError("unexpected container count")
        networks = [json.loads(line) for line in lines]
        if any(not isinstance(item, dict) for item in networks):
            raise ValueError("invalid network topology")
        report = assess_consumers(
            {"api": set(networks[0]), "worker_alerts": set(networks[1])},
            set(networks[2]),
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        report = assess_consumers({"api": set(), "worker_alerts": set()}, set())

    print(json.dumps(report, sort_keys=True))
    # Even separate Docker networks do not prove that Caddy/public routes,
    # credential distribution and API paths are isolated.
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
