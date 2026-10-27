import httpx
import pytest

from app.integrations.glpi import GLPIClient


@pytest.mark.asyncio
async def test_ticket_lookup_reads_later_pages_before_declaring_absent(monkeypatch):
    seen_ranges = []
    marker = "[n.infraops:abc]"

    def handler(request):
        seen_ranges.append(request.url.params["range"])
        start = int(request.url.params["range"].split("-", 1)[0])
        if start == 0:
            return httpx.Response(
                206,
                headers={"Content-Range": "0-99/101"},
                json=[
                    {"id": index, "entities_id": 5, "name": marker}
                    for index in range(1, 101)
                ],
            )
        return httpx.Response(
            200,
            headers={"Content-Range": "100-100/101"},
            json=[{"id": 501, "entities_id": 1, "name": f"{marker} incident"}],
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

    assert await client.find_ticket_by_name_marker(marker, 1) == 501
    assert seen_ranges == ["0-99", "100-199"]


@pytest.mark.asyncio
async def test_ticket_lookup_follows_server_capped_page_size(monkeypatch):
    seen_ranges = []
    marker = "[n.infraops:abc]"

    def handler(request):
        seen_ranges.append(request.url.params["range"])
        start = int(request.url.params["range"].split("-", 1)[0])
        if start < 100:
            return httpx.Response(
                206,
                headers={"Content-Range": f"{start}-{start + 49}/101"},
                json=[
                    {"id": index, "entities_id": 5, "name": marker}
                    for index in range(start, start + 50)
                ],
            )
        return httpx.Response(
            200,
            headers={"Content-Range": "100-100/101"},
            json=[{"id": 501, "entities_id": 1, "name": f"{marker} incident"}],
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

    assert await client.find_ticket_by_name_marker(marker, 1) == 501
    assert seen_ranges == ["0-99", "50-149", "100-199"]


@pytest.mark.asyncio
async def test_ticket_lookup_rejects_malformed_pagination_before_creating_duplicate(
    monkeypatch,
):
    def handler(_request):
        return httpx.Response(206, headers={"Content-Range": "invalid"}, json=[])

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

    with pytest.raises(RuntimeError, match="pagina"):
        await client.find_ticket_by_name_marker("[n.infraops:abc]", 1)


@pytest.mark.asyncio
async def test_ticket_lookup_does_not_assume_short_page_is_complete_without_range(
    monkeypatch,
):
    def handler(_request):
        return httpx.Response(
            200,
            json=[{"id": 1, "entities_id": 5, "name": "unrelated"}],
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

    with pytest.raises(RuntimeError, match="Content-Range"):
        await client.find_ticket_by_name_marker("[n.infraops:abc]", 1)


@pytest.mark.asyncio
async def test_ticket_lookup_rejects_range_inconsistent_with_nonempty_page(monkeypatch):
    def handler(_request):
        return httpx.Response(
            200,
            headers={"Content-Range": "0-0/0"},
            json=[{"id": 1, "entities_id": 5, "name": "unrelated"}],
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

    with pytest.raises(RuntimeError, match="pagina"):
        await client.find_ticket_by_name_marker("[n.infraops:abc]", 1)


@pytest.mark.asyncio
async def test_ticket_lookup_rejects_range_for_a_different_page(monkeypatch):
    def handler(_request):
        return httpx.Response(
            200,
            headers={"Content-Range": "10-10/11"},
            json=[{"id": 1, "entities_id": 5, "name": "unrelated"}],
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

    with pytest.raises(RuntimeError, match="pagina"):
        await client.find_ticket_by_name_marker("[n.infraops:abc]", 1)


@pytest.mark.asyncio
async def test_ticket_lookup_classifies_forbidden_response_as_permanent(monkeypatch):
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

    with pytest.raises(PermissionError, match="GLPI"):
        await client.find_ticket_by_name_marker("[n.infraops:abc]", 1)


@pytest.mark.asyncio
async def test_ticket_lookup_accepts_glpi_empty_search_without_range(monkeypatch):
    # Observed on production GLPI: an empty search returns 200, [] and no Content-Range.
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=[])),
            **kwargs,
        ),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="app", user_token="user"
    )
    client.session_token = "session"

    assert await client.find_ticket_by_name_marker("[n.infraops:abc]", 1) is None
    assert await client.list_items("Ticket/1/Document_Item") == []
