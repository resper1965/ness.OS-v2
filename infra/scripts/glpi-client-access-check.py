"""Read temporary API credentials from stdin; output only authorization results."""
import asyncio
import json
import sys

import httpx

from app.integrations.glpi import GLPIClient


async def main(accounts):
    for account in accounts:
        glpi = GLPIClient(user_token=account["token"])
        try:
            await glpi.change_active_entity(account["entity"])
            tickets = await glpi.list_items("Ticket")
            assert tickets, "Expected existing customer tickets"
            assert all(int(t["entities_id"]) == account["entity"] for t in tickets)
            assets = await glpi.list_items("Computer")
            assert all(int(a["entities_id"]) == account["entity"] for a in assets)
            other_entity = 8 if account["entity"] == 1 else 1
            try:
                await glpi.change_active_entity(other_entity)
                raise AssertionError("Cross-entity selection unexpectedly allowed")
            except httpx.HTTPStatusError as exc:
                assert exc.response.status_code in (400, 401, 403)
            except PermissionError:
                pass
            await glpi.change_active_entity(account["entity"])
            other_ticket = 2 if account["entity"] == 8 else None
            if other_ticket is None:
                # Choose a ticket from the other temporary account's exact entity.
                peer = next(a for a in accounts if a["entity"] == other_entity)
                other = GLPIClient(user_token=peer["token"])
                try:
                    await other.change_active_entity(other_entity)
                    other_ticket = (await other.list_items("Ticket"))[0]["id"]
                finally:
                    await other.kill_session()
            async with httpx.AsyncClient() as client:
                own = await client.get(f"{glpi.base_url}/Ticket/{tickets[0]['id']}", headers=glpi.headers)
                denied = await client.get(f"{glpi.base_url}/Ticket/{other_ticket}", headers=glpi.headers)
                assert own.status_code == 200
                assert denied.status_code in (401, 403, 404)
                root_asset = await client.get(f"{glpi.base_url}/Computer/1", headers=glpi.headers)
                assert root_asset.status_code in (401, 403, 404)
            print(json.dumps({"entity": account["entity"], "visible_tickets": len(tickets),
                              "own_ticket": own.status_code, "other_ticket": denied.status_code,
                              "cross_entity_selection": "denied"}))
        finally:
            await glpi.kill_session()


asyncio.run(main(json.load(sys.stdin)))
