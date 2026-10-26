"""Entrypoint for the isolated GLPI maintenance gateway."""

import os
from pathlib import Path

from app.integrations.glpi import GLPIClient, is_private_glpi_api_url
from app.integrations.glpi_boundary import create_app


def build_app():
    url = os.getenv("NESS_GLPI_MAINTENANCE_URL", "")
    if not is_private_glpi_api_url(url):
        raise ValueError("A private GLPI API URL is required")
    if url != "http://glpi-maintenance-private/apirest.php":
        raise ValueError("The dedicated GLPI host is required")

    raw_ids = os.getenv("NESS_GLPI_MAINTENANCE_APPROVED_IDS", "")
    parts = raw_ids.split(",")
    if (
        not 1 <= len(parts) <= 5
        or any(
            not part.isascii() or not part.isdecimal() or int(part) <= 0
            for part in parts
        )
        or len({int(part) for part in parts}) != len(parts)
    ):
        raise ValueError("Maintenance allowlist requires one to five unique IDs")

    secret_dir = Path(os.getenv("NESS_GLPI_MAINTENANCE_SECRET_DIR", "/run/secrets"))

    def secret(name):
        try:
            value = (secret_dir / name).read_text(encoding="utf-8").strip()
        except OSError:
            raise ValueError("A required maintenance secret is unavailable") from None
        if not value:
            raise ValueError("A required maintenance secret is empty")
        return value

    app_token = secret("glpi_app_token")
    user_token = secret("glpi_user_token")
    bearer_token = secret("gateway_bearer_token")

    return create_app(
        lambda: GLPIClient(base_url=url, app_token=app_token, user_token=user_token),
        entity_id=1,
        approved_ids={int(part) for part in parts},
        bearer_token=bearer_token,
    )
