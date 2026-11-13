import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from cli.contabo.api_client import ContaboAPIClient
from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import require_platform_admin

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_platform_admin)])


def get_contabo_client() -> ContaboAPIClient:
    try:
        return ContaboAPIClient()
    except Exception as error:
        logger.error("Failed to initialize Contabo client: %s", type(error).__name__)
        raise HTTPException(
            status_code=500,
            detail="Contabo CLI integration failed or missing credentials.",
        )


def _contabo_failure(operation: str, error: Exception) -> HTTPException:
    logger.error("Contabo %s failed: %s", operation, type(error).__name__)
    return HTTPException(status_code=502, detail="Contabo API indisponível.")


# --- Infrastructure ---
@router.get("/compute", response_model=List[Dict[str, Any]])
def list_instances(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List all VPS instances from Contabo."""
    try:
        response = client.get("/compute/instances")
        return response.get("data", [])
    except Exception as error:
        raise _contabo_failure("instance list", error)


@router.get("/compute/{instance_id}/snapshots")
def list_snapshots(
    instance_id: int, client: ContaboAPIClient = Depends(get_contabo_client)
):
    """List snapshots for a specific instance."""
    try:
        response = client.get(f"/compute/instances/{instance_id}/snapshots")
        return response.get("data", [])
    except Exception as error:
        raise _contabo_failure("snapshot list", error)


@router.get("/storage", response_model=List[Dict[str, Any]])
def list_storage(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List all Object Storages from Contabo."""
    try:
        response = client.get("/object-storages")
        return response.get("data", [])
    except Exception as error:
        raise _contabo_failure("object storage list", error)


@router.get("/summary")
def get_cloud_summary(client: ContaboAPIClient = Depends(get_contabo_client)):
    """Aggregated summary of cloud resources for the dashboard header."""
    try:
        instances = client.get("/compute/instances").get("data", [])
        storages = client.get("/object-storages").get("data", [])

        running = sum(1 for i in instances if i.get("status") == "running")
        total_storage = sum(float(s.get("totalSpaceTb", 0)) for s in storages)

        return {
            "instances": {
                "total": len(instances),
                "running": running,
                "stopped": len(instances) - running,
            },
            "storage": {"total_tb": total_storage, "buckets": len(storages)},
        }
    except Exception as error:
        raise _contabo_failure("cloud summary", error)


@router.get("/firewall", response_model=List[Dict[str, Any]])
def list_firewalls(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List all Cloud Firewalls."""
    try:
        response = client.get("/firewalls")
        return response.get("data", [])
    except Exception as error:
        raise _contabo_failure("firewall list", error)


@router.get("/networks", response_model=List[Dict[str, Any]])
def list_networks(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List all Private Networks (VPC)."""
    try:
        response = client.get("/private-networks")
        return response.get("data", [])
    except Exception as error:
        raise _contabo_failure("network list", error)


@router.get("/images", response_model=List[Dict[str, Any]])
def list_images(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List all OS images (Standard and Custom)."""
    try:
        # Images are under compute in OpenAPI
        response = client.get("/compute/images")
        return response.get("data", [])
    except Exception as error:
        raise _contabo_failure("image list", error)


@router.get("/audits", response_model=List[Dict[str, Any]])
def list_audits(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List cloud activity audits for health tracking."""
    try:
        response = client.get("/compute/instances/audits")
        return response.get("data", [])
    except Exception as error:
        raise _contabo_failure("audit list", error)


SNAPSHOT_MAX_AGE_DAYS = 7
STORAGE_WARN_PCT = 80
AUDIT_DAYS = 7
_INACTIVE = {"uninstalled", "cancelled"}


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_overview(raw: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Pure: Contabo payloads -> fleet totals, risks, timeline. Read-only data, no secrets."""
    instances = [i for i in raw["instances"] if i.get("status") not in _INACTIVE]
    fw_of: dict[int, list[str]] = {}
    for fw in raw["firewalls"]:
        for inst in fw.get("instances") or []:
            fw_of.setdefault(inst.get("instanceId"), []).append(fw.get("name") or "")
    net_of: dict[int, list[str]] = {}
    for net in raw["networks"]:
        for inst in net.get("instances") or []:
            net_of.setdefault(inst.get("instanceId"), []).append(net.get("name") or "")

    rows, risks = [], []
    for i in instances:
        iid, name = i.get("instanceId"), i.get("displayName") or i.get("name") or str(
            i.get("instanceId")
        )
        snaps = raw["snapshots"].get(iid)
        last = max(
            (d for d in (_parse(s.get("createdDate")) for s in snaps or []) if d),
            default=None,
        )
        age = (now - last).days if last else None
        row = {
            "id": iid,
            "name": name,
            "status": i.get("status"),
            "product": i.get("productName"),
            "region": i.get("regionName") or i.get("region"),
            "datacenter": i.get("dataCenter"),
            "ipv4": ((i.get("ipConfig") or {}).get("v4") or {}).get("ip"),
            "cpu": i.get("cpuCores"),
            "ram_gb": round((i.get("ramMb") or 0) / 1024, 1),
            "disk_gb": round((i.get("diskMb") or 0) / 1024),
            "created": i.get("createdDate"),
            "cancel_date": i.get("cancelDate"),
            "error": i.get("errorMessage") or None,
            "firewalls": fw_of.get(iid, []),
            "networks": net_of.get(iid, []),
            "snapshots": None if snaps is None else len(snaps),
            "snapshot_age_days": age,
        }
        rows.append(row)
        if row["cancel_date"]:
            risks.append(
                {
                    "level": "bad",
                    "kind": "cancel",
                    "target": name,
                    "detail": f"cancelamento marcado para {row['cancel_date']}",
                }
            )
        if row["error"] or row["status"] == "error":
            risks.append(
                {
                    "level": "bad",
                    "kind": "error",
                    "target": name,
                    "detail": row["error"] or "status error",
                }
            )
        elif row["status"] != "running":
            risks.append(
                {
                    "level": "warn",
                    "kind": "status",
                    "target": name,
                    "detail": f"status {row['status']}",
                }
            )
        if not row["firewalls"]:
            risks.append(
                {
                    "level": "warn",
                    "kind": "firewall",
                    "target": name,
                    "detail": "sem firewall do provedor",
                }
            )
        if snaps is not None and (age is None or age > SNAPSHOT_MAX_AGE_DAYS):
            risks.append(
                {
                    "level": "warn",
                    "kind": "snapshot",
                    "target": name,
                    "detail": (
                        "sem snapshot"
                        if age is None
                        else f"último snapshot há {age} dias"
                    ),
                }
            )

    storages = []
    for s in raw["storages"]:
        st = raw["storage_stats"].get(s.get("objectStorageId")) or {}
        pct = st.get("usedSpacePercentage")
        item = {
            "id": s.get("objectStorageId"),
            "name": s.get("displayName") or s.get("objectStorageId"),
            "status": s.get("status"),
            "region": s.get("region"),
            "total_tb": s.get("totalPurchasedSpaceTB"),
            "used_tb": st.get("usedSpaceTB"),
            "used_pct": pct,
            "objects": st.get("numberOfObjects"),
            "cancel_date": s.get("cancelDate"),
        }
        storages.append(item)
        if isinstance(pct, (int, float)) and pct >= STORAGE_WARN_PCT:
            risks.append(
                {
                    "level": "warn",
                    "kind": "storage",
                    "target": item["name"],
                    "detail": f"{pct:.0f}% ocupado",
                }
            )

    names = {r["id"]: r["name"] for r in rows}
    fw_names = {f.get("firewallId"): f.get("name") for f in raw["firewalls"]}
    events = []
    for kind, items in raw["audits"].items():
        for a in items:
            target = (
                names.get(a.get("instanceId"))
                or fw_names.get(a.get("firewallId"))
                or str(a.get("instanceId") or a.get("firewallId") or "")
            )
            events.append(
                {
                    "at": a.get("timestamp"),
                    "kind": kind,
                    "action": a.get("action"),
                    "target": target,
                    "by": a.get("username") or a.get("changedBy"),
                    "fields": sorted((a.get("changes") or {}).keys()),
                }
            )
    events.sort(key=lambda e: e["at"] or "", reverse=True)

    statuses: dict[str, int] = {}
    for r in rows:
        statuses[r["status"] or "unknown"] = (
            statuses.get(r["status"] or "unknown", 0) + 1
        )
    risks.sort(key=lambda r: r["level"] != "bad")
    return {
        "observed_at": now.isoformat(),
        "fleet": {
            "instances": len(rows),
            "statuses": statuses,
            "cpu": sum(r["cpu"] or 0 for r in rows),
            "ram_gb": round(sum(r["ram_gb"] for r in rows), 1),
            "disk_gb": sum(r["disk_gb"] for r in rows),
            "regions": sorted({r["region"] for r in rows if r["region"]}),
            "firewalls": len(raw["firewalls"]),
            "networks": len(raw["networks"]),
        },
        "risks": risks,
        "instances": sorted(rows, key=lambda r: r["name"]),
        "storages": storages,
        "events": events[:100],
    }


@router.get("/overview")
def get_overview(client: ContaboAPIClient = Depends(get_contabo_client)):
    """Painel da Contabo: frota, riscos, armazenamento e mudanças dos últimos 7 dias."""
    now = datetime.now(timezone.utc)
    since = {
        "startDate": (now - timedelta(days=AUDIT_DAYS)).date().isoformat(),
        "size": 100,
        "orderBy": "timestamp:desc",
    }
    page = {"size": 200}
    try:
        with ThreadPoolExecutor(max_workers=8) as ex:
            f = {
                "instances": ex.submit(client.get, "/compute/instances", page),
                "storages": ex.submit(client.get, "/object-storages", page),
                "firewalls": ex.submit(client.get, "/firewalls", page),
                "networks": ex.submit(client.get, "/private-networks", page),
                "a_instance": ex.submit(client.get, "/compute/instances/audits", since),
                "a_firewall": ex.submit(client.get, "/firewalls/audits", since),
                "a_snapshot": ex.submit(client.get, "/compute/snapshots/audits", since),
            }
            data = {k: v.result().get("data", []) for k, v in f.items()}
            live = [
                i["instanceId"]
                for i in data["instances"]
                if i.get("status") not in _INACTIVE
            ]
            snap_f = {
                iid: ex.submit(client.get, f"/compute/instances/{iid}/snapshots")
                for iid in live
            }
            stat_f = {
                s["objectStorageId"]: ex.submit(
                    client.get, f"/object-storages/{s['objectStorageId']}/stats"
                )
                for s in data["storages"]
            }
            snapshots = {iid: fu.result().get("data", []) for iid, fu in snap_f.items()}
            stats = {}
            for sid, fu in stat_f.items():
                d = fu.result().get("data") or [{}]
                stats[sid] = d[0] if isinstance(d, list) else d
    except Exception as error:
        raise _contabo_failure("overview", error)
    return build_overview(
        {
            "instances": data["instances"],
            "storages": data["storages"],
            "firewalls": data["firewalls"],
            "networks": data["networks"],
            "snapshots": snapshots,
            "storage_stats": stats,
            "audits": {
                "instância": data["a_instance"],
                "firewall": data["a_firewall"],
                "snapshot": data["a_snapshot"],
            },
        },
        now,
    )
