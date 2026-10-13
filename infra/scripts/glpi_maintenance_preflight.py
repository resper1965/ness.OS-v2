#!/usr/bin/env python3
"""Local GLPI gateway deployment guard; does not approve network isolation."""

import ipaddress
import os
import re
import stat
from pathlib import Path

_DIGEST_IMAGE = re.compile(r"^[a-zA-Z0-9._/-]+@sha256:[a-fA-F0-9]{64}$")
_RFC1918 = tuple(
    ipaddress.ip_network(cidr)
    for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


def validate(*, image: str, subnet: str, gateway_ip: str, secret_paths) -> list[str]:
    findings = []
    if not _DIGEST_IMAGE.fullmatch(image):
        findings.append("IMAGE_NOT_IMMUTABLE")

    try:
        network = ipaddress.ip_network(subnet, strict=True)
        address = ipaddress.ip_address(gateway_ip)
    except ValueError:
        findings.append("INVALID_PRIVATE_NETWORK")
    else:
        if not isinstance(network, ipaddress.IPv4Network) or not any(
            network.subnet_of(private) for private in _RFC1918
        ):
            findings.append("INVALID_PRIVATE_NETWORK")
        elif address not in network:
            findings.append("IP_OUTSIDE_SUBNET")
        elif address in {network.network_address, network.broadcast_address}:
            findings.append("IP_NOT_USABLE")

    if len(secret_paths) != 3:
        findings.append("SECRET_COUNT_INVALID")
    for path in secret_paths:
        try:
            mode = path.lstat().st_mode
            if not stat.S_ISREG(mode) or mode & 0o077 or path.stat().st_size == 0:
                findings.append("SECRET_UNSAFE")
        except OSError:
            findings.append("SECRET_UNSAFE")
    return findings


def main() -> int:
    config = {
        "image": os.getenv("NINF_API_IMAGE", ""),
        "subnet": os.getenv("NESS_GLPI_MAINTENANCE_SUBNET", ""),
        "gateway_ip": os.getenv("NESS_GLPI_MAINTENANCE_GATEWAY_IP", ""),
        "secret_paths": [
            Path(os.getenv(name, ""))
            for name in (
                "NESS_GLPI_MAINTENANCE_APP_TOKEN_FILE",
                "NESS_GLPI_MAINTENANCE_USER_TOKEN_FILE",
                "NESS_GLPI_MAINTENANCE_BEARER_FILE",
            )
        ],
    }
    findings = validate(**config)
    print("PASS_LOCAL_PREFLIGHT" if not findings else "BLOCKED_" + ",".join(findings))
    # A passing local preflight still requires a fresh route/subnet test and
    # a real GLPI/Hub negative matrix before activating the account.
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
