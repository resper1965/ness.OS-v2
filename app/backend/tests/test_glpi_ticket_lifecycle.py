import json

import httpx
import pytest

from app.integrations.glpi import GLPIClient, GLPITransientError


def _client(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    client = GLPIClient(
        base_url="http://glpi/apirest.php", app_token="a", user_token="u"
    )
    client.session_token = "s"
    client.user_id = 94
    return client


def _list(rows):
    return httpx.Response(
        200,
        headers={"Content-Range": f"0-{len(rows) - 1}/{len(rows)}"} if rows else {},
        json=rows,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "users,followups,expected",
    [
        ([{"type": 2}], [], True),
        ([{"type": 1}], [{"users_id": 94}], False),
        ([{"type": 1}], [{"users_id": 7}], True),
    ],
)
async def test_has_technician(monkeypatch, users, followups, expected):
    def handler(request):
        if request.url.path.endswith("/Ticket_User"):
            return _list(users)
        return _list(followups)

    assert await _client(monkeypatch, handler).has_technician(5) is expected


@pytest.mark.asyncio
async def test_solve_ticket_posts_solution_then_status_5(monkeypatch):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"id": 1})

    await _client(monkeypatch, handler).solve_ticket(5, "ok")
    assert [(m, p) for m, p, _ in calls] == [
        ("POST", "/apirest.php/ITILSolution"),
        ("PUT", "/apirest.php/Ticket/5"),
    ]
    assert calls[1][2] == {"input": {"id": 5, "status": 5}}


@pytest.mark.asyncio
async def test_reopen_ticket_comments_then_status_2(monkeypatch):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"id": 1})

    await _client(monkeypatch, handler).reopen_ticket(5, "voltou")
    assert [(m, p) for m, p, _ in calls] == [
        ("POST", "/apirest.php/ITILFollowup"),
        ("PUT", "/apirest.php/Ticket/5"),
    ]
    assert calls[1][2] == {"input": {"id": 5, "status": 2}}


@pytest.mark.asyncio
async def test_unavailable_glpi_is_transient(monkeypatch):
    client = _client(monkeypatch, lambda r: httpx.Response(503))
    with pytest.raises(GLPITransientError):
        await client.solve_ticket(5, "ok")
