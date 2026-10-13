"""The maintenance gateway must fail closed before any GLPI request."""

import pytest
from fastapi.testclient import TestClient

from app.integrations import glpi_maintenance_runtime
from app.integrations.glpi_maintenance_runtime import build_app


def test_runtime_rejects_public_glpi_url(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "NESS_GLPI_MAINTENANCE_URL", "https://n-ticket.ness.com.br/apirest.php"
    )
    monkeypatch.setenv("NESS_GLPI_MAINTENANCE_SECRET_DIR", str(tmp_path))
    monkeypatch.setenv("NESS_GLPI_MAINTENANCE_APPROVED_IDS", "41")

    with pytest.raises(ValueError, match="private GLPI API URL"):
        build_app()


def test_runtime_requires_all_secret_files(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "NESS_GLPI_MAINTENANCE_URL", "http://glpi-maintenance-private/apirest.php"
    )
    monkeypatch.setenv("NESS_GLPI_MAINTENANCE_SECRET_DIR", str(tmp_path))
    monkeypatch.setenv("NESS_GLPI_MAINTENANCE_APPROVED_IDS", "41")

    with pytest.raises(ValueError, match="maintenance secret"):
        build_app()


@pytest.mark.parametrize("ids", ["", "0", "41,41", "41,041", "1,2,3,4,5,6", "41,x"])
def test_runtime_rejects_invalid_or_broad_allowlist(monkeypatch, tmp_path, ids):
    monkeypatch.setenv(
        "NESS_GLPI_MAINTENANCE_URL", "http://glpi-maintenance-private/apirest.php"
    )
    monkeypatch.setenv("NESS_GLPI_MAINTENANCE_SECRET_DIR", str(tmp_path))
    monkeypatch.setenv("NESS_GLPI_MAINTENANCE_APPROVED_IDS", ids)

    with pytest.raises(ValueError, match="one to five"):
        build_app()


def test_runtime_reads_secrets_and_denies_unknown_computer(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "NESS_GLPI_MAINTENANCE_URL", "http://glpi-maintenance-private/apirest.php"
    )
    monkeypatch.setenv("NESS_GLPI_MAINTENANCE_SECRET_DIR", str(tmp_path))
    monkeypatch.setenv("NESS_GLPI_MAINTENANCE_APPROVED_IDS", "41")
    (tmp_path / "glpi_app_token").write_text("test-app-token")
    (tmp_path / "glpi_user_token").write_text("test-user-token")
    (tmp_path / "gateway_bearer_token").write_text("test-gateway-token")

    app = build_app()
    response = TestClient(app).get(
        "/v1/computers/42", headers={"Authorization": "Bearer test-gateway-token"}
    )

    assert response.status_code == 404
    assert "test-user-token" not in response.text


@pytest.mark.parametrize(("returned_entity", "expected_status"), [(1, 200), (5, 404)])
def test_runtime_factory_synthetic_entity_matrix(
    monkeypatch, tmp_path, returned_entity, expected_status
):
    monkeypatch.setenv(
        "NESS_GLPI_MAINTENANCE_URL", "http://glpi-maintenance-private/apirest.php"
    )
    monkeypatch.setenv("NESS_GLPI_MAINTENANCE_SECRET_DIR", str(tmp_path))
    monkeypatch.setenv("NESS_GLPI_MAINTENANCE_APPROVED_IDS", "41")
    for name in ("glpi_app_token", "glpi_user_token", "gateway_bearer_token"):
        (tmp_path / name).write_text(f"test-{name}")

    observed = []

    class FakeGLPI:
        def __init__(self, *, base_url, app_token, user_token):
            assert base_url == "http://glpi-maintenance-private/apirest.php"
            assert app_token == "test-glpi_app_token"
            assert user_token == "test-glpi_user_token"
            self.base_url = base_url

        async def change_active_entity(self, entity_id):
            observed.append(("entity", entity_id))

        async def get_item(self, itemtype, item_id):
            observed.append(("get", itemtype, item_id))
            return {"id": 41, "name": "synthetic", "entities_id": returned_entity}

        async def kill_session(self):
            observed.append(("logout",))
            return True

    monkeypatch.setattr(glpi_maintenance_runtime, "GLPIClient", FakeGLPI)
    client = TestClient(build_app())
    denied = client.get("/v1/computers/41", headers={"Authorization": "Bearer wrong"})
    assert denied.status_code == 401
    assert observed == []

    response = client.get(
        "/v1/computers/41",
        headers={"Authorization": "Bearer test-gateway_bearer_token"},
    )
    assert response.status_code == expected_status
    assert observed == [("entity", 1), ("get", "Computer", 41), ("logout",)]
    if expected_status == 200:
        assert response.json() == {"id": 41, "name": "synthetic", "entities_id": 1}
    assert "test-glpi_user_token" not in response.text
