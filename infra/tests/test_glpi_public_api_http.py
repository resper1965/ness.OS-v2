"""Exercise the versioned GLPI Caddy site with synthetic auth and upstreams."""

import io
import pathlib
import shlex
import subprocess
import sys
import tarfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "app" / "Caddyfile").read_text()
START = SOURCE.index("n-ticket.ness.com.br {")
END = SOURCE.index("# Psono Community", START)
SITE = SOURCE[START:END]
CONFIG = (
    SITE.replace("n-ticket.ness.com.br {", ":8080 {", 1)
    .replace("authentik-server:9000", "127.0.0.1:9000")
    .replace("ninf-glpi:80", "127.0.0.1:9001")
    + '\n:9000 {\n    respond "AUTH_OK" 200\n}\n'
    + ':9001 {\n    respond "UPSTREAM_OK" 200\n}\n'
)

PROBE = """#!/bin/sh
set -eu
mkdir -p /tmp/ness-glpi-http
tar -xf - -C /tmp/ness-glpi-http
caddy run --config /tmp/ness-glpi-http/Caddyfile --adapter caddyfile >/tmp/ness-glpi-http/caddy.log 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
sleep 1
for path in /apirest.php/initSession /APIRest.PHP/initSession /apirest.php%2FinitSession /apirest.php%252FinitSession /apirest%2Ephp/initSession /apirest%252Ephp/initSession /apirest%25252Ephp/initSession /api%2572est.php/initSession /apirest.php%3B/initSession; do
    result="$(wget -S -O - -T 3 "http://127.0.0.1:8080$path" 2>&1 || true)"
    printf '%s' "$result" | grep -q 'HTTP/1.1 403' || { echo "FAIL: API path $path was not denied"; printf '%s\n' "$result" | head -c 500; tail -10 /tmp/ness-glpi-http/caddy.log; exit 1; }
    printf '%s' "$result" | grep -q 'UPSTREAM_OK' && { echo "FAIL: API path $path reached upstream"; exit 1; }
done
result="$(wget -S -O - -T 3 http://127.0.0.1:8080/front/central.php 2>&1 || true)"
printf '%s' "$result" | grep -q 'UPSTREAM_OK' || { echo 'FAIL: GLPI UI did not reach upstream'; exit 1; }
result="$(wget -S -O - -T 3 'http://127.0.0.1:8080/front/central.php?example=%25' 2>&1 || true)"
printf '%s' "$result" | grep -q 'UPSTREAM_OK' || { echo 'FAIL: GLPI UI query was blocked'; exit 1; }
echo 'PASS: public GLPI API denied; UI reached synthetic upstream'
"""


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: test_glpi_public_api_http.py SSH_TARGET SSH_KEY")
    bundle = io.BytesIO()
    with tarfile.open(fileobj=bundle, mode="w") as archive:
        payload = CONFIG.encode()
        info = tarfile.TarInfo("Caddyfile")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    command = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
        "-i", sys.argv[2], sys.argv[1],
        "sudo -n docker run --rm --network none -i --entrypoint sh caddy:2-alpine -c "
        + shlex.quote(PROBE),
    ]
    result = subprocess.run(command, input=bundle.getvalue(), capture_output=True)
    if result.returncode:
        print(result.stdout.decode(errors="replace"), end="")
        print(result.stderr.decode(errors="replace"), end="", file=sys.stderr)
    else:
        print(result.stdout.decode().strip())
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
