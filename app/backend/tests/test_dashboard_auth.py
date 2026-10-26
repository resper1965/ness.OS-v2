from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.dashboard import router
from app.core.dependencies import get_current_user
from app.models.users import UserRole


def _client() -> tuple[FastAPI, TestClient]:
    app = FastAPI()
    app.include_router(router)
    return app, TestClient(app)


def test_dashboard_problems_requires_authentication():
    _, client = _client()

    assert client.get("/api/dashboard/problems").status_code == 401
    assert client.get("/api/dashboard/sources").status_code == 401


def test_dashboard_problems_rejects_client_role():
    app, client = _client()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role=UserRole.cliente
    )

    assert client.get("/api/dashboard/problems").status_code == 403
    assert client.get("/api/dashboard/sources").status_code == 403
