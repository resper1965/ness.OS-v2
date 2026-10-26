import httpx
import pytest

from app.integrations.glpi import GLPIClient, GLPIPermanentError, GLPITransientError


@pytest.mark.asyncio
async def test_entity_selection_rejects_success_response_with_wrong_effective_entity(
    monkeypatch,
):
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
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="app", user_token="user"
    )
    client.session_token = "session"

    with pytest.raises(PermissionError, match="entity"):
        await client.change_active_entity(1)

    assert requests == [
        ("POST", "/apirest.php/changeActiveEntities"),
        ("GET", "/apirest.php/getActiveEntities"),
        ("GET", "/apirest.php/killSession"),
    ]


@pytest.mark.asyncio
async def test_entity_selection_accepts_one_nonrecursive_entity_with_metadata(
    monkeypatch,
):
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
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="app", user_token="user"
    )
    client.session_token = "session"

    await client.change_active_entity(1)
    assert client.session_token == "session"


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["get_item", "list_items"])
async def test_glpi_resource_permission_denial_is_permanent(monkeypatch, operation):
    def handler(request):
        return httpx.Response(403, request=request)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="app", user_token="user"
    )
    client.session_token = "session"

    with pytest.raises(GLPIPermanentError):
        if operation == "get_item":
            await client.get_item("Ticket", 10)
        else:
            await client.list_items("Ticket")


@pytest.mark.asyncio
async def test_glpi_connection_failure_is_transient(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("unavailable", request=request)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="app", user_token="user"
    )

    with pytest.raises(RuntimeError) as error:
        await client.init_session()
    assert type(error.value).__name__ == "GLPITransientError"


@pytest.mark.asyncio
async def test_glpi_get_item_connection_failure_is_transient(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("unavailable", request=request)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="app", user_token="user"
    )
    client.session_token = "session"

    with pytest.raises(GLPITransientError):
        await client.get_item("Computer", 41)


@pytest.mark.asyncio
async def test_glpi_list_items_connection_failure_is_transient(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("unavailable", request=request)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="app", user_token="user"
    )
    client.session_token = "session"

    with pytest.raises(GLPITransientError):
        await client.list_items("Ticket/41/ITILSolution")


@pytest.mark.asyncio
async def test_glpi_list_items_reads_all_pages_when_server_caps_page_size(monkeypatch):
    requested = []

    def handler(request):
        start = int(request.url.params["range"].split("-")[0])
        requested.append(start)
        stop = min(start + 50, 120)
        return httpx.Response(
            206,
            json=[{"id": item_id} for item_id in range(start, stop)],
            headers={"Content-Range": f"{start}-{stop - 1}/120"},
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="app", user_token="user"
    )
    client.session_token = "session"

    items = await client.list_items("Ticket/41/ITILSolution")

    assert [item["id"] for item in items] == list(range(120))
    assert requested == [0, 50, 100]


@pytest.mark.asyncio
async def test_glpi_list_items_rejects_empty_page_before_reported_total(monkeypatch):
    requested = []

    def handler(request):
        start = int(request.url.params["range"].split("-")[0])
        requested.append(start)
        page = [{"id": item_id} for item_id in range(50)] if start == 0 else []
        return httpx.Response(
            206,
            json=page,
            headers={"Content-Range": "0-49/120"},
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="app", user_token="user"
    )
    client.session_token = "session"

    with pytest.raises(RuntimeError, match="incomplete"):
        await client.list_items("Ticket/41/ITILSolution")

    assert requested == [0, 50]


@pytest.mark.asyncio
async def test_glpi_list_items_rejects_short_page_without_total(monkeypatch):
    def handler(_request):
        return httpx.Response(200, json=[{"id": 1}])

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="app", user_token="user"
    )
    client.session_token = "session"

    with pytest.raises(RuntimeError, match="pagination"):
        await client.list_items("Computer")


@pytest.mark.asyncio
async def test_glpi_list_items_rejects_range_for_another_page(monkeypatch):
    def handler(_request):
        return httpx.Response(
            206,
            json=[{"id": 1}],
            headers={"Content-Range": "1-1/2"},
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="app", user_token="user"
    )
    client.session_token = "session"

    with pytest.raises(RuntimeError, match="pagination"):
        await client.list_items("Computer")


@pytest.mark.asyncio
async def test_entity_selection_connection_failure_is_transient_and_closes_session(
    monkeypatch,
):
    def handler(request):
        if request.url.path.endswith("/killSession"):
            return httpx.Response(200, json=True)
        raise httpx.ConnectError("unavailable", request=request)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="app", user_token="user"
    )
    client.session_token = "session"

    with pytest.raises(GLPITransientError):
        await client.change_active_entity(1)
    assert client.session_token is None
