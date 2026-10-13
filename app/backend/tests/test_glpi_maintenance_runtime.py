"""The maintenance gateway must fail closed before any GLPI request."""

import pytest
from fastapi.testclient import TestClient

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
