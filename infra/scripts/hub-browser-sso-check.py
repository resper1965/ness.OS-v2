"""Real browser password, TOTP, consent, tenant access and logout validation.

Requires a protected manifest of disposable Authentik accounts with TOTP devices.
Never use this manifest format to collect existing users' credentials.
"""

import hashlib
import hmac
import json
from pathlib import Path
import struct
import sys
import time

from playwright.sync_api import sync_playwright


def totp(key):
    digest = hmac.new(
        bytes.fromhex(key), struct.pack(">Q", int(time.time()) // 30), hashlib.sha1
    ).digest()
    offset = digest[-1] & 15
    return str(
        (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000
    ).zfill(6)


rows = json.loads(Path(sys.argv[1]).read_text())
if len(sys.argv) > 3:
    rows = [row for row in rows if row["tenant"] == sys.argv[3]]
results = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=sys.argv[2], headless=True)
    try:
        for user in rows:
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            page.goto("https://hub.ness.com.br", wait_until="domcontentloaded")
            page.get_by_role("button", name="Entrar com SSO").click()
            page.locator("input[name=uidField]").fill(user["username"])
            page.get_by_role("button", name="Log in", exact=True).click()
            page.get_by_label("Password", exact=True).fill(user["password"])
            page.get_by_role("button", name="Continue", exact=True).click()
            page.locator("input[name=code]").wait_for()
            page.locator("input[name=code]").fill(totp(user["key"]))
            page.get_by_role("button", name="Continue", exact=True).click()
            consent = page.get_by_role(
                "heading", name="You're about to sign into Hub n.infraops."
            )
            consent.or_(page.get_by_role("button", name="Sair da conta")).wait_for()
            if consent.is_visible():
                page.get_by_role("button", name="Continue", exact=True).click()
            page.get_by_role("button", name="Sair da conta").wait_for(timeout=30000)
            me = context.request.get("https://hub.ness.com.br/api/auth/me")
            assert me.status == 200
            assert me.json()["role"] == ("noc" if user["group"] == "noc" else "cliente")
            incidents = context.request.get(
                "https://hub.ness.com.br/api/incidents?limit=100"
            )
            assert incidents.status == 200
            items = incidents.json()["incidents"]
            if user["group"] != "noc":
                assert all(i["client"].lower() == user["tenant"] for i in items)
                other = "alupar" if user["tenant"] == "cavan" else "cavan"
                assert (
                    context.request.get(
                        "https://hub.ness.com.br/api/incidents?tenant_id=" + other
                    ).status
                    == 403
                )
            page.get_by_text("Incidentes", exact=True).first.click()
            try:
                page.locator('a[href*="ticket.form.php"]').first.wait_for(timeout=15000)
            except Exception:
                page.screenshot(path="/tmp/ness-hub-browser-failure.png")
                print(page.locator("body").inner_text()[:3500], flush=True)
                raise RuntimeError("Incident screen has no ticket links") from None
            page.screenshot(path="/tmp/ness-hub-browser-" + user["tenant"] + ".png")
            if user["group"] != "noc":
                assert page.get_by_text("Todos os Clientes", exact=True).count() == 0
                assert "Sem conexão" not in page.locator("body").inner_text()
            page.get_by_role("button", name="Sair da conta").click()
            page.wait_for_url("**sso.ness.com.br/**")
            page.get_by_role(
                "heading", name="You've logged out of Hub n.infraops."
            ).wait_for(timeout=15000)
            assert (
                context.request.get("https://hub.ness.com.br/api/auth/me").status == 401
            )
            # Global Authentik logout is a separate action from RP/application logout.
            page.goto(
                "https://sso.ness.com.br/if/flow/default-invalidation-flow/",
                wait_until="domcontentloaded",
            )
            page.locator("input[name=uidField]").wait_for(timeout=20000)
            page.goto("https://hub.ness.com.br", wait_until="domcontentloaded")
            page.get_by_role("button", name="Entrar com SSO").click()
            page.locator("input[name=uidField]").wait_for(timeout=15000)
            results.append(
                {
                    "tenant": user["tenant"],
                    "password_totp_consent": "passed",
                    "role": me.json()["role"],
                    "incidents": len(items),
                    "logout_cookie": "passed",
                    "logout_application": "passed",
                    "logout_central_separate_action": "passed",
                }
            )
            print(json.dumps(results[-1]), flush=True)
            context.close()
    finally:
        browser.close()
Path(
    "/tmp/ness-hub-browser-result"
    + ("-" + sys.argv[3] if len(sys.argv) > 3 else "")
    + ".json"
).write_text(json.dumps({"status": "ok", "cases": results}))
