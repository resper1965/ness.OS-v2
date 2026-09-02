"""Fail-closed, read-only readiness probe for the private GLPI API route."""

import asyncio

from app.integrations.glpi import GLPIClient


async def _main() -> None:
    client = GLPIClient()
    result = await client.readiness_probe()
    print(
        "status={status} mode={mode} transport={transport} "
        "entities={entity_count} categories={category_count} "
        "writes={write_operations} session_closed={session_closed}".format(**result)
    )


if __name__ == "__main__":
    asyncio.run(_main())
