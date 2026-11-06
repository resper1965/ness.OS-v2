import httpx
import pytest

from app.integrations.zabbix import ZabbixClient, is_zabbix_api_url


def _client(
    monkeypatch,
    handler,
    *,
    url="https://zabbix.internal/api_jsonrpc.php",
    token="secret-token",
):
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    return ZabbixClient(url=url, token=token)


@pytest.mark.parametrize(
    "url",
    (
        "http://zabbix/api_jsonrpc.php",
        "http://127.0.0.1/api_jsonrpc.php",
        "https://zabbix.internal/api_jsonrpc.php/",
        "https://zabbix.example/api_jsonrpc.php",
    ),
)
def test_explicit_zabbix_api_urls_are_accepted(url):
    assert is_zabbix_api_url(url)


@pytest.mark.parametrize(
    "url",
    (
        "https://zabbix.example/",
        "https://zabbix.example/zabbix.php",
        "https://user:secret@zabbix.example/api_jsonrpc.php",
        "https://zabbix.example/api_jsonrpc.php?token=secret",
        "file:///api_jsonrpc.php",
    ),
)
def test_frontend_or_malformed_zabbix_urls_are_rejected(url):
    assert not is_zabbix_api_url(url)


def test_zabbix_client_verifies_tls_by_default():
    client = ZabbixClient(
        url="https://zabbix.internal/api_jsonrpc.php", token="secret-token"
    )

    assert client.verify_ssl is True


@pytest.mark.asyncio
async def test_readiness_probe_verifies_public_and_authenticated_reads(monkeypatch):
    requests = []

    def handler(request):
        payload = request.read().decode()
        requests.append((request.method, request.headers, payload))
        if '"method":"apiinfo.version"' in payload:
            assert "Authorization" not in request.headers
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "result": "7.0.18", "id": 1},
            )
        if '"method":"host.get"' in payload:
            assert request.headers["Authorization"] == "Bearer secret-token"
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "result": [{"hostid": "1"}], "id": 2},
            )
        raise AssertionError("método JSON-RPC inesperado")

    result = await _client(monkeypatch, handler).readiness_probe()

    assert result == {
        "status": "ready",
        "mode": "read-only",
        "transport": "json-rpc",
        "version": "7.0.18",
        "authenticated": True,
        "visible_host_sample_count": 1,
        "write_operations": 0,
    }
    assert [request[0] for request in requests] == ["POST", "POST"]


@pytest.mark.asyncio
async def test_missing_token_is_rejected_before_http(monkeypatch):
    def handler(request):
        raise AssertionError(f"HTTP não deveria ser chamado: {request.url}")

    client = _client(monkeypatch, handler, token="")

    with pytest.raises(RuntimeError, match="token Zabbix não configurado"):
        await client.readiness_probe()


@pytest.mark.asyncio
async def test_not_authorized_fails_closed_without_exposing_token(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        payload = request.read().decode()
        if '"method":"apiinfo.version"' in payload:
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "result": "7.0.18", "id": 1},
            )
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32602,
                    "message": "Invalid params.",
                    "data": "Not authorized.",
                },
                "id": 2,
            },
        )

    with pytest.raises(RuntimeError) as exc_info:
        await _client(monkeypatch, handler).readiness_probe()

    assert str(exc_info.value) == "Probe falhou: token Zabbix não autorizado"
    assert "secret-token" not in str(exc_info.value)
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_frontend_html_is_distinguished_from_operational_api(monkeypatch):
    def handler(request):
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text="<!doctype html><title>Zabbix</title>",
        )

    with pytest.raises(
        RuntimeError, match="frontend acessível, API JSON-RPC indisponível"
    ):
        await _client(monkeypatch, handler).readiness_probe()


@pytest.mark.asyncio
async def test_redirect_fails_closed_without_following(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(
            302,
            headers={"Location": "https://sso.example/application/o/authorize/"},
        )

    with pytest.raises(RuntimeError, match="redirecionamento recusado"):
        await _client(monkeypatch, handler).readiness_probe()

    assert requests == ["/api_jsonrpc.php"]


@pytest.mark.asyncio
async def test_unexpected_json_rpc_error_is_sanitized(monkeypatch):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32500,
                    "message": "internal error secret-token",
                },
                "id": 1,
            },
        )

    with pytest.raises(RuntimeError) as exc_info:
        await _client(monkeypatch, handler).readiness_probe()

    assert str(exc_info.value) == "Probe falhou: erro JSON-RPC do Zabbix"
    assert "secret-token" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_call_hides_json_rpc_provider_details(monkeypatch, caplog):
    def handler(_request):
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "error": {"message": "bad auth", "data": "Bearer provider-secret"},
                "id": 1,
            },
        )

    with pytest.raises(RuntimeError, match="Zabbix API indisponível") as error:
        await _client(monkeypatch, handler)._call("host.get", {})

    assert "provider-secret" not in str(error.value)
    assert "provider-secret" not in caplog.text


ACCESS_ID = "access-id.access"
ACCESS_SECRET = "access-secret-value"


def _set_access(monkeypatch, client_id, secret):
    from app.integrations import zabbix

    monkeypatch.setattr(zabbix.settings, "zabbix_access_client_id", client_id)
    monkeypatch.setattr(zabbix.settings, "zabbix_access_client_secret", secret)


def _ok_handler(seen):
    def handler(request):
        seen.append(request.headers)
        payload = request.read().decode()
        result = "7.0.18" if "apiinfo.version" in payload else []
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "result": result,
                "id": 1 if "apiinfo" in payload else 2,
            },
        )

    return handler


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("client_id", "secret", "expected"),
    (
        (ACCESS_ID, ACCESS_SECRET, True),
        ("", "", False),
        (ACCESS_ID, "", False),
        ("", ACCESS_SECRET, False),
    ),
)
async def test_zabbix_client_sends_access_headers(
    monkeypatch, client_id, secret, expected
):
    _set_access(monkeypatch, client_id, secret)
    seen = []
    client = _client(monkeypatch, _ok_handler(seen))

    await client._call("host.get", {})
    await client.readiness_probe()

    assert len(seen) == 3  # _call + 2 chamadas do probe
    for headers in seen:
        assert ("cf-access-client-id" in headers) is expected
        assert ("cf-access-client-secret" in headers) is expected
        if expected:
            assert headers["cf-access-client-id"] == ACCESS_ID
            assert headers["cf-access-client-secret"] == ACCESS_SECRET


@pytest.mark.asyncio
async def test_secops_zabbix_call_sends_access_headers(monkeypatch):
    from app.api.routers import secops
    from app.integrations import zabbix

    _set_access(monkeypatch, ACCESS_ID, ACCESS_SECRET)
    monkeypatch.setattr(zabbix.settings, "zabbix_api_token", "secret-token")
    seen = []
    _client(monkeypatch, _ok_handler(seen))

    assert await secops._zabbix("host.get", {}) == []

    assert seen[0]["cf-access-client-id"] == ACCESS_ID
    assert seen[0]["cf-access-client-secret"] == ACCESS_SECRET
    assert seen[0]["authorization"] == "Bearer secret-token"


@pytest.mark.asyncio
async def test_access_secret_not_logged_on_failure(monkeypatch, caplog):
    _set_access(monkeypatch, ACCESS_ID, ACCESS_SECRET)

    def handler(request):
        return httpx.Response(403, text="denied")

    client = _client(monkeypatch, handler)
    with caplog.at_level("DEBUG"), pytest.raises(RuntimeError) as exc:
        await client._call("host.get", {})
    with caplog.at_level("DEBUG"), pytest.raises(RuntimeError):
        await client.readiness_probe()

    assert ACCESS_SECRET not in caplog.text
    assert ACCESS_SECRET not in str(exc.value)
