from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.core import router
from app.core.dependencies import get_current_user
from app.models.users import UserRole


def _client() -> tuple[FastAPI, TestClient]:
    app = FastAPI()
    app.include_router(router)
    return app, TestClient(app)


@pytest.mark.parametrize("path", ["/api/core/overview", "/api/core/kpis"])
def test_global_core_metrics_require_authentication(path):
    _, client = _client()

    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", ["/api/core/overview", "/api/core/kpis"])
def test_global_core_metrics_reject_client_role(path):
    app, client = _client()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role=UserRole.cliente
    )

    assert client.get(path).status_code == 403


def test_module_catalog_remains_available_to_authenticated_clients():
    app, client = _client()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role=UserRole.cliente
    )

    assert client.get("/api/core/modules").status_code == 200
