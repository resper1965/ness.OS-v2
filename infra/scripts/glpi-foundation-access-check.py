"""Prove internal project/runbook access with disposable real GLPI accounts."""
import asyncio
import json
import sys

import httpx

from app.integrations.glpi import GLPIClient


async def main(accounts):
    assert {a["entity"] for a in accounts} == {0, 1, 8}
    for account in accounts:
        glpi = GLPIClient(user_token=account["token"])
        try:
            await glpi.change_active_entity(account["entity"])
            checks = []
            async with httpx.AsyncClient(timeout=20) as client:
                for kind, identity in [("Project", 1), ("ProjectTask", 1)] + [
                    ("KnowbaseItem", n) for n in range(7, 12)
                ]:
                    response = await client.get(
                        f"{glpi.base_url}/{kind}/{identity}", headers=glpi.headers
                    )
                    allowed = account["entity"] == 0
                    assert response.status_code == 200 if allowed else response.status_code in (401, 403, 404), (
                        account["entity"], kind, identity, response.status_code
                    )
                    checks.append({"type": kind, "id": identity, "status": response.status_code})
            print(json.dumps({"entity": account["entity"], "checks": checks}))
        finally:
            await glpi.kill_session()


asyncio.run(main(json.load(sys.stdin)))
