"""Reconcile monitored identities with GLPI without matching shared IP addresses."""

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from ipaddress import ip_address

from sqlalchemy import select, update

from app.database import SessionLocal
from app.integrations.glpi import GLPIClient
from app.integrations.zabbix import ZabbixClient
from app.models import Asset, AssetType, Incident


def host_marker(comment):
    match = re.search(r"Zabbix Host ID:\s*(\d+)", comment or "")
    return match.group(1) if match else None


def exact_match(index, host_id, entity):
    candidates = index.get(host_id, [])
    if len(candidates) == 1 and int(candidates[0]["entities_id"]) == entity:
        return candidates[0]
    return None


def assert_existing_asset_identity(asset, row):
    """Never silently rebind an existing monitored asset to another GLPI identity."""
    if asset.customer_id != row["customer_id"]:
        raise ValueError(
            "Existing asset identity changed; manual reconciliation required"
        )
    previous = asset.tags or {}
    incoming = row["tags"]
    for key in ("glpi_entity_id", "glpi_itemtype", "glpi_item_id"):
        if previous.get(key) is not None and str(previous[key]) != str(
            incoming.get(key)
        ):
            raise ValueError(
                "Existing asset identity changed; manual reconciliation required"
            )


def scoped_hosts(hostids):
    if hostids is None:
        return None
    if not 1 <= len(hostids) <= 5 or len(set(hostids)) != len(hostids):
        raise ValueError("Scope requires one to five unique host IDs")
    if any(
        not isinstance(h, str) or not h.isascii() or not h.isdecimal() or int(h) <= 0
        for h in hostids
    ):
        raise ValueError("Scope requires positive numeric host IDs")
    return hostids


async def reconcile(apply=False, hostids=None):
    hostids = scoped_hosts(hostids)
    from app.workers.alerts import (
        customer_from_hostgroups,
        resolve_customer_name,
        resolve_glpi_entity_id,
    )

    hosts = await ZabbixClient()._call(
        "host.get",
        {
            "filter": {"status": 0},
            **({"hostids": hostids} if hostids is not None else {}),
            "output": ["hostid", "host", "name"],
            "selectHostGroups": ["name"],
            "selectTags": "extend",
            "selectInterfaces": ["ip", "dns", "main"],
            "selectInventory": ["os", "location"],
        },
    )
    if hostids is not None and {h["hostid"] for h in hosts} != set(hostids):
        raise ValueError("Source hosts differ from requested scope")
    glpi = GLPIClient()
    indexed = {}
    try:
        for entity in range(12):
            await glpi.change_active_entity(entity)
            groups = {int(g["id"]): g["name"] for g in await glpi.list_items("Group")}
            technical_groups = {
                (g["itemtype"], int(g["items_id"])): int(g["groups_id"])
                for g in await glpi.list_items("Group_Item")
                if int(g["type"]) == 2
            }
            for itemtype in ("Computer", "NetworkEquipment"):
                for item in await glpi.list_items(itemtype):
                    # GLPI may expose recursively shared parent assets. Never map them to a child.
                    if int(item["entities_id"]) != entity:
                        continue
                    marker = host_marker(item.get("comment"))
                    if marker:
                        group_id = technical_groups.get((itemtype, int(item["id"])), 0)
                        indexed.setdefault(marker, []).append(
                            {
                                **item,
                                "itemtype": itemtype,
                                "groups_id_tech": group_id,
                                "owner_group_name": groups.get(group_id),
                            }
                        )
    finally:
        await glpi.kill_session()
    rows, gaps = [], []
    for host in hosts:
        source_tags = {t["tag"]: t["value"] for t in host.get("tags", [])}
        try:
            customer = customer_from_hostgroups(
                host["hostgroups"]
            ) or resolve_customer_name(host["host"], source_tags)
            entity = resolve_glpi_entity_id(customer)
        except ValueError:
            gaps.append({"host_id": host["hostid"], "reason": "unmapped_customer"})
            continue
        if source_tags.get("scope") == "uat":
            gaps.append(
                {"host_id": host["hostid"], "reason": "synthetic_check_not_equipment"}
            )
            continue
        item = exact_match(indexed, host["hostid"], entity)
        if not item:
            gaps.append(
                {
                    "host_id": host["hostid"],
                    "name": host["name"],
                    "entity": entity,
                    "reason": (
                        "conflicting_mapping"
                        if indexed.get(host["hostid"])
                        else "missing_glpi"
                    ),
                    "tags": source_tags,
                    "groups": host["hostgroups"],
                }
            )
            continue
        interface = next(
            (i for i in host.get("interfaces", []) if i["main"] == "1"), {}
        )
        address = interface.get("ip")
        try:
            address = str(ip_address(address))
        except ValueError:
            address = None
        inventory = host.get("inventory") or {}
        if isinstance(inventory, list):
            inventory = {}
        os_name = inventory.get("os", "") or source_tags.get("technology", "")
        typ = (
            AssetType.NETWORK_DEVICE
            if item["itemtype"] == "NetworkEquipment"
            else (
                AssetType.WINDOWS
                if "windows" in os_name.lower()
                else (
                    AssetType.LINUX if "linux" in os_name.lower() else AssetType.UNKNOWN
                )
            )
        )
        rows.append(
            {
                "zabbix_host_id": host["hostid"],
                "hostname": host["host"],
                "customer_id": customer.lower().strip(),
                "customer_name": customer,
                "ip_address": address,
                "fqdn": interface.get("dns") or None,
                "os_family": (
                    "windows"
                    if "windows" in os_name.lower()
                    else ("linux" if "linux" in os_name.lower() else None)
                ),
                "asset_type": typ,
                "location": source_tags.get("site")
                or inventory.get("location")
                or None,
                "tags": {
                    "source": "zabbix+glpi",
                    "glpi_itemtype": item["itemtype"],
                    "glpi_item_id": item["id"],
                    "glpi_entity_id": entity,
                    "glpi_location_id": item.get("locations_id", 0),
                    "glpi_owner_user_id": item.get("users_id_tech", 0),
                    "glpi_owner_group_id": item.get("groups_id_tech", 0),
                    "owner": source_tags.get("owner")
                    or item.get("owner_group_name")
                    or (
                        f"Responsável GLPI #{item['users_id_tech']}"
                        if item.get("users_id_tech")
                        else None
                    ),
                    "source_tags": source_tags,
                    "source_os": os_name,
                },
            }
        )
    linked = 0
    if apply:
        async with SessionLocal() as session:
            async with session.begin():
                for row in rows:
                    asset = (
                        await session.execute(
                            select(Asset).where(
                                Asset.zabbix_host_id == row["zabbix_host_id"]
                            )
                        )
                    ).scalar_one_or_none()
                    if asset is None:
                        asset = Asset(**row)
                        session.add(asset)
                    else:
                        assert_existing_asset_identity(asset, row)
                        row["tags"] = {**(asset.tags or {}), **row["tags"]}
                        for key, value in row.items():
                            setattr(asset, key, value)
                    asset.last_seen = datetime.now(timezone.utc)
                    await session.flush()
                    result = await session.execute(
                        update(Incident)
                        .where(
                            Incident.host_id == asset.zabbix_host_id,
                            Incident.tags["ninf_customer_name"].astext
                            == asset.customer_name,
                        )
                        .values(asset_id=asset.id)
                    )
                    linked += result.rowcount
    return {
        "mode": "applied" if apply else "dry-run",
        "mapped_assets": len(rows),
        "linked_incidents": linked,
        "gaps": gaps,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--hostids", nargs="+")
    args = parser.parse_args()
    print(
        json.dumps(asyncio.run(reconcile(args.apply, args.hostids)), ensure_ascii=False)
    )
