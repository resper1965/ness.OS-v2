import httpx
import pytest

from app.integrations.glpi import GLPIClient
from app.workers.alerts import customer_from_hostgroups, resolve_glpi_entity_id


@pytest.mark.parametrize(
    "name,entity", [("Cavan", 8), ("Alupar PE", 5), ("Alupar CO", 6), ("Ness", 0)]
)
def test_explicit_entity_mapping(name, entity):
    assert resolve_glpi_entity_id(name) == entity


@pytest.mark.parametrize("name", ["Outros", "unknown", "not-cavan", "fake-alupar"])
def test_unmapped_customer_cannot_write_to_root(name):
    with pytest.raises(ValueError, match="entidade"):
        resolve_glpi_entity_id(name)


def test_authoritative_groups_select_child_entity():
    assert (
        customer_from_hostgroups(
            [{"name": "[ Alupar ]"}, {"name": "[ Alupar PE ] [ Lima ]"}]
        )
        == "Alupar PE"
    )


def test_conflicting_customer_groups_are_rejected():
    with pytest.raises(ValueError, match="distintos"):
        customer_from_hostgroups([{"name": "[ Cavan ]"}, {"name": "[ TBE ]"}])


def test_alert_task_is_explicitly_loaded_and_resolution_is_routed():
    from app.workers.celery_app import celery_app

    assert "app.workers.alerts" in celery_app.conf.include
    assert (
        celery_app.conf.task_routes["app.workers.tasks.process_ticket_resolution"][
            "queue"
        ]
        == "alerts.primary"
    )


def test_new_problem_event_gets_new_ticket_identity():
    from app.core.fingerprint import generate_event_fingerprint
    from app.models.schemas import ZabbixAlertPayload

    first = ZabbixAlertPayload(
        event_id="10",
        host_id="1",
        host_name="test",
        trigger_id="2",
        trigger_name="test",
    )
    replay = first.model_copy()
    next_problem = first.model_copy(update={"event_id": "11"})
    assert generate_event_fingerprint(first) == generate_event_fingerprint(replay)
    assert generate_event_fingerprint(first) != generate_event_fingerprint(next_problem)


def test_generic_zabbix_group_does_not_override_customer():
    assert (
        customer_from_hostgroups(
            [{"name": "Zabbix servers"}, {"name": "[ Alupar PE ]"}]
        )
        == "Alupar PE"
    )


@pytest.mark.asyncio
async def test_entity_selection_does_not_enable_recursive_access(monkeypatch):
    import json

    def handler(request):
        assert request.url.path == "/apirest.php/changeActiveEntities"
        assert json.loads(request.content) == {"entities_id": 8, "is_recursive": False}
        return httpx.Response(403)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="a", user_token="u"
    )
    client.session_token = "session"
    with pytest.raises(httpx.HTTPStatusError):
        await client.change_active_entity(8)


@pytest.mark.asyncio
async def test_service_is_requester_without_broadening_followup_rights(monkeypatch):
    import json

    def handler(request):
        if request.url.path.endswith("initSession"):
            assert request.url.params["get_full_session"] == "true"
            return httpx.Response(
                200, json={"session_token": "session", "session": {"glpiID": 94}}
            )
        assert json.loads(request.content)["input"]["_users_id_requester"] == 94
        return httpx.Response(201, json={"id": 1})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="a", user_token="u"
    )
    assert await client.create_ticket("title", "content", entity_id=8) == {"id": 1}
