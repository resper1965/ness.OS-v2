"""Helpers for the browser session cookie used by the Hub."""

from urllib.parse import urlsplit

from fastapi import HTTPException, Request, Response, status

from app.config import get_settings

SESSION_COOKIE_NAME = "ninf_session"
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def require_trusted_origin(request: Request) -> None:
    """Reject unsafe browser requests that did not originate from the Hub."""
    if request.method not in _UNSAFE_METHODS:
        return
    configured_url = urlsplit(get_settings().dashboard_base_url)
    expected_origin = f"{configured_url.scheme}://{configured_url.netloc}"
    if request.headers.get("origin") != expected_origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origem da sessao nao autorizada",
        )


def set_session_cookie(response: Response, token: str) -> None:
    """Store a JWT in a host-only cookie that JavaScript cannot read."""
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.jwt_expire_hours * 60 * 60,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )


def clear_session_cookie(response: Response) -> None:
    """Expire the browser session cookie using the same security attributes."""
    settings = get_settings()
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
