"""Read-only operational proof that two Hub DB sessions serialize one advisory lock."""

import asyncio
from hashlib import blake2b
import json
from time import monotonic

from sqlalchemy import text

from app.database import SessionLocal


async def main() -> None:
    identity = b"ness-glpi-lock-probe:2026-10-13"
    key = int.from_bytes(blake2b(identity, digest_size=8).digest(), "big", signed=True)
    first_acquired = asyncio.Event()

    async def hold_first() -> None:
        async with SessionLocal() as session:
            async with session.begin():
                await session.execute(text("SET LOCAL lock_timeout = '5s'"))
                await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
                first_acquired.set()
                await asyncio.sleep(0.25)
    async def acquire_second() -> float:
        async with SessionLocal() as session:
            async with session.begin():
                await session.execute(text("SET LOCAL lock_timeout = '5s'"))
                started = monotonic()
                await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
                return monotonic() - started

    first = asyncio.create_task(hold_first())
    await first_acquired.wait()
    second = asyncio.create_task(acquire_second())
    _, second_wait_seconds = await asyncio.gather(first, second)
    serialized = second_wait_seconds >= 0.15
    print(json.dumps({"mode": "advisory_lock_no_writes", "serialized": serialized}))
    if not serialized:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
