import pytest
from fastapi import HTTPException

from app.core.webhook_auth import verify_key


@pytest.mark.parametrize(
    "configured,supplied,status",
    [
        ("", None, 503),
        ("", "guess", 503),
        ("secret", None, 401),
        ("secret", "wrong", 401),
    ],
)
def test_webhook_rejects_missing_or_invalid_key(configured, supplied, status):
    with pytest.raises(HTTPException) as exc:
        verify_key(configured, supplied)
    assert exc.value.status_code == status


def test_webhook_accepts_configured_key():
    verify_key("secret", "secret")
