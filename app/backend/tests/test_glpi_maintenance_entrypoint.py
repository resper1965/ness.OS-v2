"""The maintenance process must drop root after loading root-only secrets."""

import importlib
from types import SimpleNamespace

import pytest


def test_entrypoint_loads_secrets_before_dropping_to_nessops(monkeypatch):
    entrypoint = importlib.import_module("app.integrations.glpi_maintenance_entrypoint")
    calls = []
    identity = {"uid": 0, "gid": 0}
    app = object()

    def setgid(gid):
        calls.append(("setgid", gid))
        identity["gid"] = gid

    def setuid(uid):
        calls.append(("setuid", uid))
        identity["uid"] = uid

    monkeypatch.setattr(entrypoint.os, "geteuid", lambda: identity["uid"])
    monkeypatch.setattr(entrypoint.os, "getegid", lambda: identity["gid"])
    monkeypatch.setattr(
        entrypoint.pwd,
        "getpwnam",
        lambda name: SimpleNamespace(pw_uid=999, pw_gid=999),
    )
    monkeypatch.setattr(entrypoint, "build_app", lambda: calls.append("load") or app)
    monkeypatch.setattr(
        entrypoint.os, "setgroups", lambda groups: calls.append(("groups", groups))
    )
    monkeypatch.setattr(entrypoint.os, "setgid", setgid)
    monkeypatch.setattr(entrypoint.os, "setuid", setuid)
    monkeypatch.setattr(
        entrypoint.uvicorn,
        "run",
        lambda actual_app, **kwargs: calls.append(
            ("serve", actual_app, identity["uid"], identity["gid"], kwargs)
        ),
    )

    entrypoint.main()

    assert calls == [
        "load",
        ("groups", []),
        ("setgid", 999),
        ("setuid", 999),
        ("serve", app, 999, 999, {"host": "0.0.0.0", "port": 8000}),
    ]


def test_entrypoint_refuses_nonroot_before_loading_secrets(monkeypatch):
    entrypoint = importlib.import_module("app.integrations.glpi_maintenance_entrypoint")
    monkeypatch.setattr(entrypoint.os, "geteuid", lambda: 999)
    monkeypatch.setattr(
        entrypoint,
        "build_app",
        lambda: pytest.fail("nonroot must not read root-only secrets"),
    )

    with pytest.raises(RuntimeError, match="must start as root"):
        entrypoint.main()
