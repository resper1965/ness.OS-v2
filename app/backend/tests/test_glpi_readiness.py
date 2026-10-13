import httpx
import pytest

from app.integrations.glpi import GLPIClient, is_private_glpi_api_url


def test_explicit_glpi_credentials_do_not_load_unrelated_application_settings(
    monkeypatch,
):
    import app.integrations.glpi as glpi_module

    monkeypatch.setattr(
        glpi_module,
        "get_settings",
        lambda: (_ for _ in ()).throw(AssertionError("settings must not load")),
    )

    client = GLPIClient(
        base_url="http://glpi-maintenance-private/apirest.php",
        app_token="app",
        user_token="user",
    )

    assert client.base_url == "http://glpi-maintenance-private/apirest.php"


def _client(monkeypatch, handler, *, base_url="http://ninf-glpi/apirest.php"):
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    return GLPIClient(base_url=base_url, app_token="app", user_token="user")


@pytest.mark.parametrize(
    "url",
    (
        "http://ninf-glpi/apirest.php",
        "http://127.0.0.1/apirest.php",
        "https://glpi.internal/apirest.php/",
    ),
)
def test_private_glpi_api_urls_are_accepted(url):
    assert is_private_glpi_api_url(url)


@pytest.mark.parametrize(
    "url",
    (
        "https://n-ticket.ness.com.br/apirest.php",
        "http://user:secret@ninf-glpi/apirest.php",
        "http://ninf-glpi/",
        "file:///apirest.php",
    ),
)
def test_public_or_malformed_glpi_api_urls_are_rejected(url):
    assert not is_private_glpi_api_url(url)


@pytest.mark.asyncio
async def test_readiness_probe_uses_only_get_and_closes_session(monkeypatch):
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path))
        if request.url.path.endswith("/initSession"):
            return httpx.Response(200, json={"session_token": "session"})
        if request.url.path.endswith("/getMyEntities"):
            return httpx.Response(200, json={"myentities": [{"id": 1}]})
        if request.url.path.endswith("/KnowbaseItemCategory/"):
            return httpx.Response(200, json=[{"id": 2, "name": "Runbooks"}])
        if request.url.path.endswith("/killSession"):
            return httpx.Response(200, json={})
        raise AssertionError(f"request inesperado: {request.url.path}")

    result = await _client(monkeypatch, handler).readiness_probe()

    assert result == {
        "status": "ready",
        "mode": "dry-run",
        "transport": "private",
        "entity_count": 1,
        "category_count": 1,
        "write_operations": 0,
        "session_closed": True,
    }
    assert requests == [
        ("GET", "/apirest.php/initSession"),
        ("GET", "/apirest.php/getMyEntities"),
        ("GET", "/apirest.php/KnowbaseItemCategory/"),
        ("GET", "/apirest.php/killSession"),
    ]


@pytest.mark.asyncio
async def test_public_route_is_rejected_before_http(monkeypatch):
    def handler(request):
        raise AssertionError(f"HTTP não deveria ser chamado: {request.url}")

    client = _client(
        monkeypatch,
        handler,
        base_url="https://n-ticket.ness.com.br/apirest.php",
    )

    with pytest.raises(RuntimeError, match="host privado"):
        await client.readiness_probe()


@pytest.mark.asyncio
async def test_redirect_to_sso_fails_closed_without_following(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(
            302,
            headers={"Location": "https://sso.example/application/o/authorize/"},
        )

    with pytest.raises(RuntimeError, match="GLPI sessão indisponível"):
        await _client(monkeypatch, handler).readiness_probe()

    assert requests == ["/apirest.php/initSession"]


@pytest.mark.asyncio
async def test_glpi_session_failure_hides_provider_details(monkeypatch, caplog):
    def handler(_request):
        raise RuntimeError("Authorization: Bearer provider-secret")

    with pytest.raises(RuntimeError, match="GLPI sessão indisponível") as error:
        await _client(monkeypatch, handler).init_session()

    assert "provider-secret" not in str(error.value)
    assert "provider-secret" not in caplog.text


@pytest.mark.asyncio
async def test_invalid_read_response_still_closes_session(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request.url.path)
        if request.url.path.endswith("/initSession"):
            return httpx.Response(200, json={"session_token": "session"})
        if request.url.path.endswith("/getMyEntities"):
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/killSession"):
            return httpx.Response(200, json={})
        raise AssertionError(f"request inesperado: {request.url.path}")

    with pytest.raises(RuntimeError, match="GLPI leitura de entidades indisponível"):
        await _client(monkeypatch, handler).readiness_probe()

    assert requests[-1] == "/apirest.php/killSession"


@pytest.mark.asyncio
async def test_probe_fails_when_session_cannot_be_closed(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/initSession"):
            return httpx.Response(200, json={"session_token": "session"})
        if request.url.path.endswith("/getMyEntities"):
            return httpx.Response(200, json={"myentities": []})
        if request.url.path.endswith("/KnowbaseItemCategory/"):
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/killSession"):
            return httpx.Response(500, json={"error": "failed"})
        raise AssertionError(f"request inesperado: {request.url.path}")

    with pytest.raises(RuntimeError, match="não foi encerrada"):
        await _client(monkeypatch, handler).readiness_probe()


@pytest.mark.asyncio
async def test_missing_tokens_are_rejected_before_http(monkeypatch):
    def handler(request):
        raise AssertionError(f"HTTP não deveria ser chamado: {request.url}")

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    client = GLPIClient(
        base_url="http://ninf-glpi/apirest.php",
        app_token="",
        user_token="",
    )

    with pytest.raises(RuntimeError, match="tokens GLPI não configurados"):
        await client.readiness_probe()


@pytest.mark.asyncio
async def test_ticket_marker_search_returns_single_exact_entity_match(monkeypatch):
    def handler(request):
        assert request.url.path.endswith("/Ticket/")
        assert request.url.params["searchText[name]"] == "[n.infraops:abc]"
        assert request.url.params["searchText[entities_id]"] == "8"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 321,
                    "name": "[n.infraops:abc] [AIOps] Teste",
                    "entities_id": 8,
                }
            ],
        )

    client = _client(monkeypatch, handler)
    client.session_token = "session"
    client.headers["Session-Token"] = "session"

    assert await client.find_ticket_by_name_marker("[n.infraops:abc]", 8) == 321


@pytest.mark.asyncio
async def test_ticket_marker_search_fails_closed_on_duplicates(monkeypatch):
    def handler(request):
        return httpx.Response(
            200,
            json=[
                {"id": 321, "name": "[n.infraops:abc] one", "entities_id": 8},
                {"id": 322, "name": "[n.infraops:abc] two", "entities_id": 8},
            ],
        )

    client = _client(monkeypatch, handler)
    client.session_token = "session"
    client.headers["Session-Token"] = "session"

    with pytest.raises(RuntimeError, match="tickets idempotentes duplicados"):
        await client.find_ticket_by_name_marker("[n.infraops:abc]", 8)
