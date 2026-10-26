"""Apply the tenant-qualified client entry rule in Authentik's shell.

Existing operator bindings remain intact. Hub endpoints independently enforce
tenant scope. A local protected snapshot supports removal of the added binding.
"""

import json
import os
from pathlib import Path

from django.db import transaction
from authentik.core.models import Application
from authentik.policies.models import PolicyBinding
from authentik.policies.expression.models import ExpressionPolicy

app = Application.objects.get(slug="hub")
assert app.policy_engine_mode == "any", "Review policy composition before applying"
snapshot = Path("/tmp/ness-hub-access-before.json")
if not snapshot.exists():
    with snapshot.open("x") as output:
        os.chmod(snapshot, 0o600)
        json.dump(
            {
                "app": str(app.pk),
                "mode": app.policy_engine_mode,
                "bindings": [
                    str(pk)
                    for pk in PolicyBinding.objects.filter(target=app.pk).values_list(
                        "pk", flat=True
                    )
                ],
            },
            output,
        )

expression = """tenant = request.user.attributes.get("tenant_id", "")
return isinstance(tenant, str) and tenant.strip().lower() in {"alupar", "alupar pe", "alupar co", "tbe", "target", "ltb", "bichara", "cavan", "nova energia", "numen", "tne", "ness"} and request.user.groups.filter(name="usuarios").exists()"""
with transaction.atomic():
    policy, _ = ExpressionPolicy.objects.update_or_create(
        name="NESS Hub client with assigned tenant", defaults={"expression": expression}
    )
    binding, _ = PolicyBinding.objects.get_or_create(
        target=app,
        policy=policy,
        defaults={"order": 10, "enabled": True, "negate": False},
    )
print("RESULT", json.dumps({"policy": str(policy.pk), "binding": str(binding.pk)}))
