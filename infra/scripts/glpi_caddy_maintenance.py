#!/usr/bin/env python3
"""Stage a GLPI-only Caddy maintenance candidate from a known Caddyfile."""

import argparse
import hashlib
import os
from pathlib import Path
import sys


START = "# GLPI Service Desk with Authentik Forward Auth SSO\n"
END = "# Psono Community"
MAINTENANCE = '''# GLPI Service Desk — maintenance window
n-ticket.ness.com.br {
    header Cache-Control "no-store"
    respond "GLPI temporariamente em manutenção" 503
}

'''


def build_maintenance(source: str) -> str:
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("GLPI site boundaries differ from the approved Caddyfile")
    before, tail = source.split(START)
    original, after = tail.split(END)
    if original.count("n-ticket.ness.com.br {") != 1 or original.count("reverse_proxy ninf-glpi:80") != 1:
        raise ValueError("GLPI site differs from the approved Caddyfile")
    return before + MAINTENANCE + END + after


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    try:
        raw = args.source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != args.expected_sha256:
            raise ValueError("source Caddyfile hash differs from the approved version")
        candidate = build_maintenance(raw.decode("utf-8")).encode("utf-8")
        descriptor = os.open(args.candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(candidate)
    except (OSError, UnicodeError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print(f"GLPI Caddy maintenance staging BLOCKED: {reason}", file=sys.stderr)
        return 1
    print("GLPI Caddy maintenance candidate staged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
