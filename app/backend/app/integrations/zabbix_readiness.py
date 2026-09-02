"""Fail-closed, read-only readiness probe for the Zabbix JSON-RPC API."""

import asyncio

from app.integrations.zabbix import ZabbixClient


async def _main() -> None:
    result = await ZabbixClient().readiness_probe()
    print(
        "status={status} mode={mode} transport={transport} version={version} "
        "authenticated={authenticated} visible_hosts={visible_host_sample_count} "
        "writes={write_operations}".format(**result)
    )


if __name__ == "__main__":
    asyncio.run(_main())
