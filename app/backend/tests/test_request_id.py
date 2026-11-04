from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_request_id_generated_when_absent():
    rid = client.get("/").headers["x-request-id"]
    assert len(rid) == 36


def test_valid_request_id_is_propagated_even_on_errors():
    for path in ("/", "/nao-existe"):
        r = client.get(path, headers={"X-Request-ID": "abc.DEF_1-2"})
        assert r.headers["x-request-id"] == "abc.DEF_1-2"


def test_invalid_request_id_is_replaced():
    for bad in ("a b", "x" * 65, "a/b", b"\xe9"):
        r = client.get("/", headers={"X-Request-ID": bad})
        assert r.headers["x-request-id"] != bad
        assert len(r.headers["x-request-id"]) == 36


def test_unhandled_exception_500_carries_request_id():
    @app.get("/_boom_request_id")
    async def boom():
        raise RuntimeError("boom")

    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/_boom_request_id", headers={"X-Request-ID": "req-500"})
            assert r.status_code == 500
            assert r.headers["x-request-id"] == "req-500"
            assert len(c.get("/_boom_request_id").headers["x-request-id"]) == 36
    finally:
        app.router.routes.pop()


def test_streaming_and_cors_expose_keep_working():
    from fastapi.responses import StreamingResponse

    @app.get("/_stream_request_id")
    async def stream():
        async def gen():
            yield "a"
            yield "b"

        return StreamingResponse(gen(), media_type="text/event-stream")

    try:
        r = client.get(
            "/_stream_request_id",
            headers={"X-Request-ID": "sse-1", "Origin": "http://localhost:3000"},
        )
        assert r.text == "ab" and r.headers["x-request-id"] == "sse-1"
        assert "X-Request-ID" in r.headers["access-control-expose-headers"]
    finally:
        app.router.routes.pop()
