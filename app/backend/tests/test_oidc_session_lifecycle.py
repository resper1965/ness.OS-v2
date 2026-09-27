import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from jose import JWTError
from starlette.requests import Request

from app.api.routers.incidents import _load_stream_user


def _request(authorization: str = "Bearer session-token") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/incidents/stream",
            "headers": [(b"authorization", authorization.encode())],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )


def test_expired_oidc_session_is_rejected_during_stream_revalidation():
    with patch(
        "app.api.routers.incidents.verify_token", side_effect=JWTError("expired")
    ):
        user = asyncio.run(_load_stream_user(_request()))

    assert user is None


def test_inactive_oidc_user_is_rejected_during_stream_revalidation():
    class _Result:
        def scalar_one_or_none(self):
            return SimpleNamespace(id=7, is_active=False)

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def execute(self, _):
            return _Result()

    with (
        patch(
            "app.api.routers.incidents.verify_token",
            return_value={"sub": "7"},
        ),
        patch("app.api.routers.incidents.SessionLocal", return_value=_Session()),
    ):
        user = asyncio.run(_load_stream_user(_request()))

    assert user is None
