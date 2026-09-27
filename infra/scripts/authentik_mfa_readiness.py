#!/usr/bin/env python3
"""Read-only Authentik MFA inventory for the configured admin custodians."""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


def summarize_admin_mfa(required_users: list[str], authenticators: list[dict]) -> dict:
    """Return aggregate enrollment status without exposing usernames or factors."""
    required = [username.strip() for username in required_users if username.strip()]
    if len(required) < 2 or len(set(required)) != len(required):
        return {"required_count": len(required), "enrolled_count": 0, "ready": False}

    enrolled: set[str] = set()
    for authenticator in authenticators:
        user = authenticator.get("user") or {}
        username = user.get("username")
        if user.get("is_active") and username in required:
            enrolled.add(username)
    return {
        "required_count": len(required),
        "enrolled_count": len(enrolled),
        "ready": len(enrolled) == len(required),
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read_authenticators(base_url: str, token: str) -> list[dict]:
    origin = urlparse(base_url)
    if origin.scheme != "https" or not origin.netloc:
        raise ValueError("HTTPS Authentik URL required")

    opener = build_opener(_NoRedirect)
    authenticators: list[dict] = []
    for factor in ("totp", "webauthn"):
        next_url = urljoin(
            base_url.rstrip("/") + "/",
            f"api/v3/authenticators/admin/{factor}/?page_size=100",
        )
        visited: set[str] = set()
        while next_url:
            parsed = urlparse(next_url)
            if (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc):
                raise ValueError("Authenticator pagination origin changed")
            if not parsed.path.startswith("/api/v3/authenticators/admin/") or next_url in visited:
                raise ValueError("Invalid authenticator pagination link")
            visited.add(next_url)
            request = Request(
                next_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
            )
            with opener.open(request, timeout=15) as response:
                payload = json.load(response)
            authenticators.extend(payload.get("results", []))
            pagination = payload.get("pagination") or {}
            next_page = pagination.get("next") or payload.get("next")
            next_url = urljoin(base_url.rstrip("/") + "/", next_page) if next_page else ""
            if len(visited) > 100:
                raise ValueError("Too many authenticator pages")
    return authenticators


def main() -> int:
    required_users = os.environ.get("AUTHENTIK_REQUIRED_ADMIN_USERS", "").split(",")
    base_url = os.environ.get("AUTHENTIK_URL", "")
    token = os.environ.get("AUTHENTIK_TOKEN", "")
    try:
        report = summarize_admin_mfa(required_users, _read_authenticators(base_url, token))
        print(f"admin_mfa_required_count={report['required_count']}")
        print(f"admin_mfa_enrolled_count={report['enrolled_count']}")
        print(f"admin_mfa_ready={'yes' if report['ready'] else 'no'}")
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        print("admin_mfa_inventory=unavailable")
        print("admin_mfa_required_count=0")
        print("admin_mfa_enrolled_count=0")
        print("admin_mfa_ready=no")
    except Exception:
        # Keep API payloads, response bodies, and usernames out of readiness logs.
        print("admin_mfa_inventory=unavailable")
        print("admin_mfa_required_count=0")
        print("admin_mfa_enrolled_count=0")
        print("admin_mfa_ready=no")
    return 0


if __name__ == "__main__":
    sys.exit(main())
