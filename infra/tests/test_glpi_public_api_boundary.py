"""Check the compiled Caddy configuration before allowing a public GLPI API route."""

import json
import re
import sys


def main() -> int:
    config = json.load(sys.stdin)
    routes = [
        route
        for server in config["apps"]["http"]["servers"].values()
        for route in server["routes"]
        if any(
            "n-ticket.ness.com.br" in match.get("host", [])
            for match in route.get("match", [])
        )
    ]
    if len(routes) != 1:
        raise AssertionError("Expected one public GLPI site")
    site_routes = routes[0]["handle"][0]["routes"]
    if site_routes[0]["handle"][0]["handler"] == "subroute":
        site_routes = site_routes[0]["handle"][0]["routes"]
    deny = site_routes[0]
    match = deny.get("match", [{}])[0].get("path_regexp", {})
    pattern = match.get("pattern", "")
    response = deny.get("handle", [{}])[0]
    if response.get("handler") != "static_response" or response.get("status_code") != 403:
        raise AssertionError("Public GLPI API must be denied before auth/proxy")
    for path in (
        "/apirest.php/initSession",
        "/APIRest.PHP/initSession",
        "/apirest.php%2FinitSession",
        "/apirest.php%252FinitSession",
    ):
        if re.search(pattern, path) is None:
            raise AssertionError(f"GLPI API path not denied: {path}")
    if re.search(pattern, "/front/central.php") is not None:
        raise AssertionError("Normal GLPI UI path would be denied")
    print("PASS: compiled public GLPI API denial precedes auth/proxy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
