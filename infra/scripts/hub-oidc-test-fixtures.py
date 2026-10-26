"""Run inside Authentik's shell: temporary identities/grants, never human sessions.

This tests the token/callback boundary only, not interactive authentication/MFA.
The protected manifest supports exact cleanup if the verifier is interrupted.
"""

import base64
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import secrets

from django.db import transaction
from django.utils.timezone import now
from authentik.core.models import Group, User
from authentik.providers.oauth2.models import AuthorizationCode, OAuth2Provider

path = Path("/tmp/ness-hub-oidc-fixtures.json")
if os.environ.get("NESS_OIDC_CLEANUP") == "1":
    data = json.loads(path.read_text())
    for row in data:
        User.objects.filter(pk=row["user_id"], username=row["username"]).delete()
    assert not User.objects.filter(pk__in=[r["user_id"] for r in data]).exists()
    path.unlink()
    print("RESULT cleanup OK")
else:
    assert not path.exists(), "Existing manifest must be cleaned up first"
    provider = OAuth2Provider.objects.get(client_id="hub-ness")
    rows = []
    with transaction.atomic():
        for label, tenant, group in [
            ("alupar", "alupar", "usuarios"),
            ("cavan", "cavan", "usuarios"),
            ("operator", "ness", "noc"),
            ("unassigned", "", "usuarios"),
            ("disabled", "alupar", "usuarios"),
        ]:
            username = "hub-protocol-test-" + secrets.token_hex(8)
            user = User.objects.create(
                username=username,
                email=username + "@ness.invalid",
                name="Temporary hub protocol check",
                attributes={"tenant_id": tenant},
                is_active=True,
                type="internal",
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
            user.groups.add(Group.objects.get(name=group))
            verifier = secrets.token_urlsafe(48)
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                .rstrip(b"=")
                .decode()
            )
            codes = []
            for _ in range(2):
                code = secrets.token_urlsafe(48)
                AuthorizationCode.objects.create(
                    provider=provider,
                    user=user,
                    code=code,
                    expires=now() + timedelta(minutes=10),
                    auth_time=now(),
                    _scope="openid profile email groups",
                    code_challenge=challenge,
                    code_challenge_method="S256",
                )
                codes.append(code)
            rows.append(
                {
                    "label": label,
                    "tenant": tenant,
                    "user_id": user.pk,
                    "username": username,
                    "email": user.email,
                    "verifier": verifier,
                    "codes": codes,
                }
            )
        with path.open("x") as output:
            os.chmod(path, 0o600)
            json.dump(rows, output)
    print("RESULT fixtures created:", len(rows))
