import asyncio

import httpx

from app.integrations.glpi import GLPIClient


async def main() -> None:
    glpi = GLPIClient()
    try:
        await glpi.init_session()
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            response = await client.get(
                f"{glpi.base_url}/Ticket/",
                headers=glpi.headers,
                params=[
                    ("searchText[name]", "[n.infraops:probe-does-not-exist]"),
                    ("searchText[entities_id]", "8"),
                    ("only_id", "true"),
                    ("range", "0-1"),
                    ("get_hateoas", "false"),
                ],
            )
            response.raise_for_status()
            data = response.json()
            print(
                "status=ready",
                f"http_status={response.status_code}",
                f"result_type={type(data).__name__}",
                f"result_count={len(data) if isinstance(data, list) else -1}",
                "writes=0",
            )
    finally:
        if not await glpi.kill_session():
            raise RuntimeError("GLPI session cleanup failed")


asyncio.run(main())
