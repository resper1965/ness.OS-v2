from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.sql.dml import Update

from app.api.routers.auth import router as auth_router
from app.core.dependencies import get_current_user
from app.core.jwt import create_access_token
from app.core.session import SESSION_COOKIE_NAME
from app.database import get_db
from app.models.users import UserRole


class _Result:
    def __init__(self, user: SimpleNamespace) -> None:
        self.user = user

    def scalar_one_or_none(self) -> SimpleNamespace:
        return self.user


class _Db:
    def __init__(self, user: SimpleNamespace) -> None:
        self.user = user

    async def execute(self, statement: object) -> _Result | SimpleNamespace:
        if isinstance(statement, Update):
            self.user.token_version += 1
            return SimpleNamespace(rowcount=1)
        return _Result(self.user)

    async def commit(self) -> None:
        return None


def _user(*, active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=42,
        email="operator@example.invalid",
        hashed_password="test-hash",
        full_name="UAT Operator",
        role=UserRole.noc,
        tenant_id="UAT-A",
        is_active=active,
        token_version=0,
        last_login=None,
    )


def _protected_client(user: SimpleNamespace) -> TestClient:
    app = FastAPI()

    @app.get("/protected")
    async def protected(current_user=Depends(get_current_user)):
        return {"id": current_user.id}

    @app.post("/protected")
    async def mutate(current_user=Depends(get_current_user)):
        return {"id": current_user.id}

    async def override_db():
        yield _Db(user)

    app.dependency_overrides[get_db] = override_db
    return TestClient(app, base_url="https://hub.ness.com.br")


def test_http_only_cookie_authenticates_without_exposing_token() -> None:
    client = _protected_client(_user())
    client.cookies.set(
        SESSION_COOKIE_NAME,
        create_access_token(user_id=42, role=UserRole.noc.value),
    )

    assert client.get("/protected").json() == {"id": 42}


def test_bearer_authentication_remains_supported() -> None:
    client = _protected_client(_user())
    token = create_access_token(user_id=42, role=UserRole.noc.value)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_cookie_authenticated_mutation_requires_trusted_origin() -> None:
    client = _protected_client(_user())
    client.cookies.set(
        SESSION_COOKIE_NAME,
        create_access_token(user_id=42, role=UserRole.noc.value),
    )

    assert client.post("/protected").status_code == 403
    assert (
        client.post(
            "/protected", headers={"Origin": "https://hub.ness.com.br"}
        ).status_code
        == 200
    )


def test_login_returns_user_and_sets_hardened_host_only_cookie() -> None:
    user = _user()
    app = FastAPI()
    app.include_router(auth_router)

    async def override_db():
        yield _Db(user)

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, base_url="https://hub.ness.com.br")

    with patch("app.api.routers.auth._verify_password", return_value=True):
        response = client.post(
            "/api/auth/login",
            headers={"Origin": "https://hub.ness.com.br"},
            json={"email": user.email, "password": "valid"},
        )

    assert response.status_code == 200
    assert "access_token" not in response.json()
    assert response.json()["email"] == user.email
    cookie = response.headers["set-cookie"].lower()
    assert f"{SESSION_COOKIE_NAME}=" in cookie
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=strict" in cookie
    assert "domain=" not in cookie


def test_non_browser_login_preserves_bearer_automation_compatibility() -> None:
    user = _user()
    app = FastAPI()
    app.include_router(auth_router)

    async def override_db():
        yield _Db(user)

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, base_url="https://hub.ness.com.br")

    with patch("app.api.routers.auth._verify_password", return_value=True):
        response = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "valid"},
        )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert SESSION_COOKIE_NAME not in response.headers.get("set-cookie", "")


def test_login_rejects_untrusted_origin() -> None:
    user = _user()
    app = FastAPI()
    app.include_router(auth_router)

    async def override_db():
        yield _Db(user)

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, base_url="https://hub.ness.com.br")

    response = client.post(
        "/api/auth/login",
        headers={"Origin": "https://untrusted.example"},
        json={"email": user.email, "password": "valid"},
    )

    assert response.status_code == 403


def test_logout_expires_cookie_with_matching_security_attributes() -> None:
    app = FastAPI()
    app.include_router(auth_router)
    client = TestClient(app, base_url="https://hub.ness.com.br")

    response = client.post(
        "/api/auth/logout", headers={"Origin": "https://hub.ness.com.br"}
    )

    assert response.status_code == 204
    cookie = response.headers["set-cookie"].lower()
    assert f"{SESSION_COOKIE_NAME}=" in cookie
    assert "max-age=0" in cookie
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=strict" in cookie


def test_logout_revokes_the_presented_bearer_token_and_existing_copies() -> None:
    user = _user()
    app = FastAPI()
    app.include_router(auth_router)

    async def override_db():
        yield _Db(user)

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, base_url="https://hub.ness.com.br")
    token = create_access_token(
        user_id=user.id,
        role=user.role.value,
        extra_claims={"token_version": user.token_version},
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "https://hub.ness.com.br",
    }
    client.cookies.set(SESSION_COOKIE_NAME, token)

    logout_response = client.post("/api/auth/logout", headers=headers)
    protected_response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert logout_response.status_code == 204
    assert user.token_version == 1
    assert protected_response.status_code == 401


def test_malformed_token_version_is_rejected() -> None:
    client = _protected_client(_user())
    token = create_access_token(
        user_id=42,
        role=UserRole.noc.value,
        extra_claims={"token_version": "0"},
    )

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_database_migration_persists_token_version_for_existing_users() -> None:
    migration = Path(__file__).parents[1] / "app" / "migrate.py"

    assert (
        "ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0"
        in migration.read_text(encoding="utf-8")
    )


def test_frontend_never_handles_session_token() -> None:
    frontend = Path(__file__).parents[2] / "frontend" / "src"
    auth_source = (frontend / "hooks" / "useAuth.tsx").read_text()
    session_consumers = "\n".join(
        (
            auth_source,
            (frontend / "App.tsx").read_text(),
            (frontend / "components" / "PushNotificationToggle.tsx").read_text(),
        )
    )

    assert "ninf_token" not in session_consumers
    assert "localStorage" not in auth_source
    assert "stream?token=" not in session_consumers
    assert "Authorization: `Bearer ${token}`" not in session_consumers
