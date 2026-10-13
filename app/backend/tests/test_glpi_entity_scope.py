import httpx
import pytest

from app.integrations.glpi import GLPIClient


@pytest.mark.asyncio
async def test_entity_selection_rejects_success_response_with_wrong_effective_entity(monkeypatch):
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path))
        if request.url.path.endswith("/changeActiveEntities"):
            return httpx.Response(200, json=True)
        if request.url.path.endswith("/getActiveEntities"):
            return httpx.Response(
                200,
                json={
                    "active_entity": {
                        "id": 5,
                        "active_entity_recursive": False,
                        "active_entities": [{"id": 5}],
                    }
                },
            )
        if request.url.path.endswith("/killSession"):
            return httpx.Response(200, json=True)
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = GLPIClient(base_url="http://glpi/apirest.php", app_token="app", user_token="user")
    client.session_token = "session"

    with pytest.raises(PermissionError, match="entity"):
        await client.change_active_entity(1)

    assert requests == [
        ("POST", "/apirest.php/changeActiveEntities"),
        ("GET", "/apirest.php/getActiveEntities"),
        ("GET", "/apirest.php/killSession"),
    ]


@pytest.mark.asyncio
async def test_entity_selection_accepts_one_nonrecursive_entity_with_metadata(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/changeActiveEntities"):
            return httpx.Response(200, json=True)
        if request.url.path.endswith("/getActiveEntities"):
            return httpx.Response(
                200,
                json={
                    "active_entity": {
                        "id": 1,
                        "active_entity_recursive": False,
                        "active_entities": [{"id": 1, "name": "Alupar"}],
                    }
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = GLPIClient(base_url="http://glpi/apirest.php", app_token="app", user_token="user")
    client.session_token = "session"

    await client.change_active_entity(1)
    assert client.session_token == "session"
