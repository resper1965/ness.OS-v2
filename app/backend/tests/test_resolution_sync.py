from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.integrations.glpi import GLPIClient
from app.integrations.zabbix import ZabbixClient
from app.workers import resolution


@pytest.mark.asyncio
async def test_resolution_fetches_human_text_and_checks_tenant(monkeypatch):
    g = GLPIClient(base_url="http://glpi/apirest.php")
    g.change_active_entity = AsyncMock()
    g.get_item = AsyncMock(
        return_value={
            "entities_id": 8,
            "status": 5,
            "name": "[n.infraops:abc] incident",
        }
    )
    g.list_items = AsyncMock(
        return_value=[
            {
                "id": 1,
                "status": 2,
                "content": "&lt;p&gt;Serviço restaurado &amp;amp; validado&lt;/p&gt;",
            },
            {"id": 2, "status": 4, "content": "refused"},
        ]
    )
    result = await g.ticket_resolution(1, 8, "abc")
    assert result["solution"] == "Serviço restaurado & validado"
    assert result["solution_id"] == "1"
    with pytest.raises(ValueError, match="ownership"):
        await g.ticket_resolution(1, 7, "abc")


@pytest.mark.asyncio
async def test_reopened_ticket_does_not_resolve_hub():
    g = GLPIClient()
    g.change_active_entity = AsyncMock()
    g.get_item = AsyncMock(
        return_value={"entities_id": 8, "status": 2, "name": "[n.infraops:a]"}
    )
    g.list_items = AsyncMock()
    assert not (await g.ticket_resolution(1, 8, "a"))["resolved"]
    g.list_items.assert_not_called()


@pytest.mark.asyncio
async def test_ack_replay_after_lost_response_does_not_write_again():
    z = ZabbixClient()
    z._call = AsyncMock(
        return_value=[
            {
                "acknowledges": [
                    {"message": "[ness-glpi-resolution:77] restored", "action": "6"}
                ]
            }
        ]
    )
    z.acknowledge_problem = AsyncMock()
    assert (
        await z.acknowledge_resolution_once("123", "77", "restored")
        == "already_acknowledged"
    )
    z.acknowledge_problem.assert_not_called()


@pytest.mark.asyncio
async def test_ack_targets_exact_original_event():
    z = ZabbixClient()
    z._call = AsyncMock(return_value=[{"acknowledges": []}])
    z.acknowledge_problem = AsyncMock(return_value={"eventids": ["123"]})
    assert await z.acknowledge_resolution_once("123", "77", "restored") == "success"
    assert z.acknowledge_problem.call_args.args[0] == "123"
    assert "[ness-glpi-resolution:77]" in z.acknowledge_problem.call_args.args[1]


@pytest.mark.asyncio
async def test_resolution_commits_human_solution_before_ack_and_replay_is_idempotent(
    monkeypatch,
):
    incident = SimpleNamespace(
        id=42,
        fingerprint="f",
        status="open",
        tags={"ninf_customer_name": "Cavan", "ninf_zabbix_event_id": "123"},
    )
    report = SimpleNamespace(
        markdown_report="original", corrective_actions=[], embedding=[1]
    )
    session = AsyncMock()
    results = []
    for item in (incident, report, incident):
        r = MagicMock()
        r.scalar_one_or_none.return_value = item
        results.append(r)
    session.execute.side_effect = results
    session.__aenter__.return_value = session
    monkeypatch.setattr(resolution, "SessionLocal", lambda: session)
    g = MagicMock()
    g.ticket_resolution = AsyncMock(
        return_value={"resolved": True, "solution": "Restaurado", "solution_id": "9"}
    )
    g.kill_session = AsyncMock()
    monkeypatch.setattr(resolution, "GLPIClient", lambda: g)
    z = MagicMock()

    async def ack(*args):
        assert session.commit.await_count >= 1
        assert incident.tags["glpi_solution"] == "Restaurado"
        return "success"

    z.acknowledge_resolution_once = AsyncMock(side_effect=ack)
    monkeypatch.setattr(resolution, "ZabbixClient", lambda: z)
    redis = MagicMock()
    await resolution.resolve_ticket("77", redis)
    await resolution.resolve_ticket("77", redis)
    assert report.markdown_report.count("Restaurado") == 1
    assert report.corrective_actions == ["Restaurado"]
    assert report.embedding is None
    assert incident.tags["resolution_sync_status"] == "synced"
    assert redis.publish.call_count == 2


@pytest.mark.asyncio
async def test_glpi_collection_reads_all_pages(monkeypatch):
    def handler(req):
        start = int(req.url.params["range"].split("-")[0])
        return httpx.Response(
            206,
            json=[{"id": i} for i in range(start, min(start + 100, 101))],
            headers={"Content-Range": f"{start}-{min(start+99,100)}/101"},
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    g = GLPIClient(base_url="http://glpi/apirest.php")
    g.session_token = "session"
    assert len(await g.list_items("Computer")) == 101


@pytest.mark.asyncio
async def test_glpi_false_entity_response_is_denied_even_with_http_200(monkeypatch):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=False)),
            **kw,
        ),
    )
    g = GLPIClient(base_url="http://glpi/apirest.php")
    g.session_token = "session"
    with pytest.raises(PermissionError):
        await g.change_active_entity(8)
