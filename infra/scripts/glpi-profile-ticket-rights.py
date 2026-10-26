"""Read only: print effective ticket permissions of the current GLPI API identity."""

import asyncio
import json

import httpx

from app.integrations.glpi import GLPIClient


async def main() -> None:
    glpi = GLPIClient()
    try:
        await glpi.init_session()
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.get(
                f"{glpi.base_url}/getActiveProfile", headers=glpi.headers
            )
            response.raise_for_status()
            data = response.json()
        profile = data.get("active_profile") if isinstance(data, dict) else None
        if not isinstance(profile, dict):
            raise RuntimeError("GLPI profile response has an unexpected shape")
        rights = {
            key: value
            for key, value in profile.items()
            if isinstance(key, str)
            and any(part in key.lower() for part in ("ticket", "itilfollowup"))
            and isinstance(value, (int, str))
            and str(value).isdigit()
        }
        print(json.dumps({"profile_id": profile.get("id"), "rights": rights}, sort_keys=True))
    finally:
        await glpi.kill_session()


if __name__ == "__main__":
    asyncio.run(main())
