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
