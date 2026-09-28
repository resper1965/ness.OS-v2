from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routers.push import subscribe_push, unsubscribe_push
from app.models.schemas import PushSubscribeRequest, PushUnsubscribeRequest


class _Result:
    def __init__(self, *, existing=None, rowcount: int = 0) -> None:
        self._existing = existing
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self._existing


class _Db:
    def __init__(self, result: _Result) -> None:
        self.result = result
        self.statement = None
        self.committed = False

    async def execute(self, statement):
        self.statement = statement
        return self.result

    async def commit(self) -> None:
        self.committed = True

    def add(self, _value) -> None:
        return None


def _user(user_id: int, tenant_id: str = "tenant-a") -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        tenant_id=tenant_id,
        email=f"user-{user_id}@example.invalid",
    )


@pytest.mark.asyncio
async def test_subscribe_does_not_take_over_another_users_endpoint() -> None:
    db = _Db(_Result(existing=SimpleNamespace(user_id=2)))

    with pytest.raises(HTTPException) as error:
        await subscribe_push(
            PushSubscribeRequest(
                endpoint="https://push.example.invalid/subscription",
                keys={"p256dh": "public", "auth": "secret"},
            ),
            _user(1),
            db,
        )

    assert error.value.status_code == 409
    assert db.committed is False


@pytest.mark.asyncio
async def test_unsubscribe_is_scoped_to_the_current_user() -> None:
    db = _Db(_Result(rowcount=0))
    endpoint = "https://push.example.invalid/subscription"

    result = await unsubscribe_push(PushUnsubscribeRequest(endpoint=endpoint), _user(1), db)

    assert result["status"] == "not_found"
    assert db.committed is True
    assert db.statement is not None
    params = db.statement.compile().params
    assert endpoint in params.values()
    assert 1 in params.values()
