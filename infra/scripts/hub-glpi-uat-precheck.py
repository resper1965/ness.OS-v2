"""Read-only configuration inventory; run inside API and alert worker containers.

This does not authorize a synthetic alert or prove the running worker loaded
the files on disk. No network calls, database writes or secret values are used.
"""

import hashlib
import json
from pathlib import Path

import app
from app.config import get_settings


def main():
    settings = get_settings()
    app_dir = Path(app.__file__).resolve().parent
    sources = {}
    for relative in ("workers/alerts.py", "integrations/glpi.py"):
        path = app_dir / relative
        sources[relative] = hashlib.sha256(
            path.read_text().replace("\r\n", "\n").encode()
        ).hexdigest()

    required = (
        "glpi_app_token",
        "glpi_user_token",
        "zabbix_api_token",
        "gemini_api_key",
        "webhook_api_key",
    )
    print(
        json.dumps(
            {
                "mode": "configuration-only",
                "integration_verified": False,
                "writes": 0,
                "source_sha256_normalized_lf": sources,
                "configured": {
                    field: bool(getattr(settings, field).strip()) for field in required
                },
                "channels": {
                    "v1_notifications_enabled": getattr(
                        settings, "alert_notifications_enabled", None
                    ),
                    "whatsapp_recipient_configured": bool(
                        settings.whatsapp_noc_group_id
                    ),
                    "webpush_keys_configured": bool(
                        settings.vapid_private_key and settings.vapid_public_key
                    ),
                    "suppression_verified": False,
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
