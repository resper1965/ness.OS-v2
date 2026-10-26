"""Optional local flow proof against disposable PostgreSQL and Redis containers."""

import json
import os
from types import SimpleNamespace
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routers.incidents import router as incidents_router
from app.core.dependencies import get_current_user
from app.core.fingerprint import generate_event_fingerprint
from app.database import SessionLocal
from app.models import Incident, IncidentAction, UserRole
from app.models.schemas import ZabbixAlertPayload
from app.workers.alerts import _async_process_alert_v1

pytestmark = pytest.mark.skipif(
    os.getenv("NINF_LOCAL_FLOW_TEST") != "1",
    reason="requires disposable PostgreSQL and Redis with NINF_LOCAL_FLOW_TEST=1",
)


@pytest.mark.asyncio
async def test_problem_partial_glpi_failure_replay_recovery_and_tenant_scope(
    monkeypatch,
):
    for variable in ("NINF_DATABASE_URL", "NINF_REDIS_URL"):
        assert urlparse(os.environ[variable]).hostname in {"127.0.0.1", "localhost"}

    tickets = []
    calls = {"created": 0, "followups": 0}

    def external_api(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api_jsonrpc.php":
            body = json.loads(request.content)
            assert body["method"] == "host.get"
            assert body["params"]["hostids"] == ["9001"]
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": [
                        {"hostid": "9001", "hostgroups": [{"name": "[ Cavan ]"}]}
                    ],
                },
            )
        if path == "/apirest.php/initSession":
            return httpx.Response(
                200, json={"session_token": "local", "session": {"glpiID": 94}}
            )
        if path == "/apirest.php/changeActiveEntities":
            assert json.loads(request.content) == {
                "entities_id": 8,
                "is_recursive": False,
            }
            return httpx.Response(200, json=True)
        if path == "/apirest.php/getActiveEntities":
            return httpx.Response(
                200,
                json={
                    "active_entity": {
                        "id": 8,
                        "active_entity_recursive": False,
                        "active_entities": [{"id": 8}],
                    }
                },
            )
        if path == "/apirest.php/Ticket/":
            marker = request.url.params["searchText[name]"]
            matches = [ticket for ticket in tickets if marker in ticket["name"]]
            return httpx.Response(
                200,
                headers={
                    "Content-Range": f"0-{max(0, len(matches) - 1)}/{len(matches)}"
                },
                json=matches,
            )
        if path == "/apirest.php/Ticket" and request.method == "POST":
            ticket = json.loads(request.content)["input"]
            assert ticket["entities_id"] == 8
            assert "<script>" not in ticket["content"]
            assert "&lt;script&gt;" in ticket["content"]
            tickets.append({"id": 501, **ticket})
            calls["created"] += 1
            # GLPI creates the ticket, but its first response is lost.
            return httpx.Response(502)
        if path == "/apirest.php/ITILFollowup":
            calls["followups"] += 1
            return httpx.Response(201, json={"id": 601})
        if path == "/apirest.php/killSession":
            return httpx.Response(200, json=True)
        raise AssertionError(f"unexpected external request: {request.method} {path}")

    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(external_api)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )

    alert = ZabbixAlertPayload(
        event_id=str(uuid4().int),
        host_id="9001",
        host_name="<script>uat-cavan</script>",
        host_ip="10.0.0.1",
        trigger_id="9002",
        trigger_name="Local synthetic problem",
        severity=4,
        tags={"probe": "<script>synthetic</script>"},
    )
    data = alert.model_dump(mode="json")
    fingerprint = generate_event_fingerprint(alert)

    with pytest.raises(RuntimeError, match="GLPI"):
        await _async_process_alert_v1(data, fingerprint)

    async with SessionLocal() as session:
        incident = (
            await session.execute(
                select(Incident).where(Incident.fingerprint == fingerprint)
            )
        ).scalar_one()
        assert incident.deskmanager_ticket_id is None
        assert incident.tags["ninf_customer_name"] == "Cavan"

    result = await _async_process_alert_v1(data, fingerprint)
    for _ in range(3):
        replay = await _async_process_alert_v1(data, fingerprint)
        assert result["ticket_id"] == replay["ticket_id"] == 501
    assert calls == {"created": 1, "followups": 0}

    async with SessionLocal() as session:
        incidents = (
            (
                await session.execute(
                    select(Incident).where(Incident.fingerprint == fingerprint)
                )
            )
            .scalars()
            .all()
        )
        assert len(incidents) == 1
        assert incidents[0].alert_count == 1
        assert incidents[0].deskmanager_ticket_id == "501"
        actions = (
            (
                await session.execute(
                    select(IncidentAction)
                    .where(IncidentAction.incident_id == incidents[0].id)
                    .order_by(IncidentAction.id)
                )
            )
            .scalars()
            .all()
        )
        assert [action.action for action in actions] == [
            "incident_created",
            "ticket_failed",
            "ticket_reused",
        ]

    app = FastAPI()
    app.include_router(incidents_router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role=UserRole.viewer, tenant_id="cavan"
    )
    with TestClient(app) as client:
        own = client.get("/api/incidents")
        assert own.status_code == 200
        assert any(row["fingerprint"] == fingerprint for row in own.json()["incidents"])
        assert client.get("/api/incidents?tenant_id=other").status_code == 403

    recovered = await _async_process_alert_v1(
        {**data, "status": "RESOLVED"}, fingerprint
    )
    assert recovered["status"] == "source_recovered"
    async with SessionLocal() as session:
        incident = (
            await session.execute(
                select(Incident).where(Incident.fingerprint == fingerprint)
            )
        ).scalar_one()
        assert incident.status == "open"
        assert incident.deskmanager_ticket_id == "501"
        assert incident.tags["ninf_zabbix_status"] == "resolved"
