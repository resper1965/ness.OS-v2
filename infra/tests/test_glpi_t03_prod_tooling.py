"""Tests for the T03 production tooling.

The pure-Python part runs anywhere (fakes). The lab part needs `infra/tests/glpi-lab/lab.sh up`
and GLPI_LAB_URL (like the negative matrix); it runs the real PHP, probe and gateway.
"""

import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("probe", SCRIPTS / "glpi_t03_functional_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

OK_BODY = {"status": 200, "keys": ["entities_id", "id", "name"], "entities_id": 1, "id": 7}
GOOD_GW = {
    "live": {"status": 200}, "allowed:7": OK_BODY, "allowed+query": {"status": 404},
    "allowed-no-bearer": {"status": 401}, "allowed-post": {"status": 405}, "denied:9": {"status": 404},
}
TOKENS = {"app": "A" * 40, "user": "U" * 40, "bearer": "B" * 40}


def fake_runner(session=None, gateway=None):
    def runner(container, script, payload):
        if "app_tokens" in payload:
            return (session or {}).get(container, {"none": 400, "gateway": 400, "container-env": 400})
        return gateway or GOOD_GW

    return runner


def run(runner):
    return probe.run(runner, containers=["ninf-api", "worker"], tokens=TOKENS, glpi_url=None,
                     gateway_url="http://gw:8000", allowed=7, denied=[9])


def test_pass_when_hub_refused_and_gateway_exact():
    assert run(fake_runner()) == []


@pytest.mark.parametrize("status", [200, 404, 500, "URLError"])
def test_hub_login_accepted_or_unclear_fails(status):
    f = run(fake_runner(session={"worker": {"gateway": 400, "container-env": status}}))
    assert len(f) == 1 and "worker" in f[0] and "container-env" in f[0]


def test_no_app_token_tried_fails():
    assert probe.judge_session("x", {}) == ["x: no App-Token tried"]


def test_gateway_denied_id_returning_200_fails():
    gw = {**GOOD_GW, "denied:9": {"status": 200}}
    assert any("denied:9" in f for f in probe.judge_gateway(7, [9], gw))


def test_gateway_leaking_extra_field_or_wrong_entity_fails():
    for bad in ({**OK_BODY, "keys": ["entities_id", "id", "name", "x"]}, {**OK_BODY, "entities_id": 5}):
        assert any("body shape" in f for f in probe.judge_gateway(7, [9], {**GOOD_GW, "allowed:7": bad}))


def test_gateway_missing_case_fails():
    gw = dict(GOOD_GW)
    del gw["allowed+query"]
    assert probe.judge_gateway(7, [9], gw)


def test_tokens_travel_by_stdin_not_argv(monkeypatch):
    seen = {}

    def fake_run(cmd, input, **kw):
        seen.update(cmd=cmd, input=input)
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    probe.docker_runner(["sudo", "-n", "docker"])("c", "print(1)", {"user_token": "SECRET"})
    assert "SECRET" not in " ".join(seen["cmd"]) and "SECRET" in seen["input"]


def test_session_script_keeps_200_when_killsession_is_refused():
    import http.server, threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            ok = self.path.endswith("/initSession")
            body = b'{"session_token":"s"}' if ok else b"{}"
            self.send_response(200 if ok else 401)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    payload = {"user_token": "U", "app_tokens": {}, "glpi_url": f"http://127.0.0.1:{srv.server_port}", "env_token": False}
    p = subprocess.run(["python3", "-c", probe._SESSION], input=json.dumps(payload), capture_output=True, text=True)
    srv.shutdown()
    assert json.loads(p.stdout) == {"none": 200}
    assert probe.judge_session("c", {"none": 200})


# ---- lab (real GLPI 11 + real PHP + real gateway) ---------------------------------------
LAB_URL = os.getenv("GLPI_LAB_URL")
LAB = Path(os.getenv("GLPI_LAB_DIR", "/tmp/opencode/glpi-lab"))
lab = pytest.mark.skipif(not LAB_URL, reason="GLPI_LAB_URL not set")
ADMIN = (SCRIPTS / "glpi-maintenance-admin.php").read_text()
LAB_OPTS = ["--user=7", "--user-name=svc_lab_maintenance", "--profile=9", "--profile-name=lab-maintenance-ro", "--recursive=1"]


def php(*args):
    return subprocess.run(
        ["docker", "exec", "-i", "-u", "www-data", "ness-glpi-lab-glpi", "php", "--", *args],
        input=ADMIN, capture_output=True, text=True, timeout=120,
    )


def sql(q):
    p = subprocess.run(
        ["docker", "exec", "glpi-lab-glpi-db-1", "mariadb", "-uroot", "-plab-root-only", "glpi", "-N", "-B", "-e", q],
        capture_output=True, text=True, timeout=60,
    )
    return p.stdout.strip()


@lab
def test_lab_apiclient_idempotent_and_token_only_on_stdout():
    args = ["apiclient", "--client-name=t23-test", *LAB_OPTS]
    assert '"mode":"dry-run"' in php(*args).stderr
    first = php(*args, "--apply")
    assert len(first.stdout) == 40 and '"token_written":true' in first.stderr and first.stdout not in first.stderr
    again = php(*args, "--apply")
    assert again.returncode == 0 and again.stdout == "" and '"action":"none"' in again.stderr
    assert sql("select ipv4_range_start,ipv4_range_end from glpi_apiclients where name='t23-test'") == "2887711235\t2887711235"
    assert len(php(*args, "--apply", "--reset-token").stdout) == 40
    sql("delete from glpi_apiclients where name='t23-test'")


@lab
def test_lab_rotate_changes_token_and_user_toggle_readback():
    before = sql("select api_token from glpi_users where id=7")
    r = php("rotate", *LAB_OPTS, "--apply")
    assert len(r.stdout) == 40 and sql("select api_token from glpi_users where id=7") != before
    (LAB / "user_token").write_text(r.stdout)  # keep the lab consistent for the other tests
    assert '"is_active":0' in php("user", *LAB_OPTS, "--deactivate").stderr
    assert sql("select is_active from glpi_users where id=7") == "0"
    assert '"is_active":1' in php("user", *LAB_OPTS, "--activate").stderr
    assert php("user", "--user=7", "--user-name=nope", "--activate").returncode == 1
    assert php("user", *LAB_OPTS).returncode == 1


@lab
def test_lab_client_toggle_readback():
    assert '"is_active":0' in php("client", "--id=1", "--deactivate").stderr
    assert sql("select is_active from glpi_apiclients where id=1") == "0"
    assert '"is_active":1' in php("client", "--id=1", "--activate").stderr
    assert php("client", "--id=999", "--activate").returncode == 1


@lab
def test_lab_profile_reduced_to_computer_read():
    sql("update glpi_profilerights set rights=13 where profiles_id=9 and name='computer'; "
        "update glpi_profilerights set rights=1 where profiles_id=9 and name='ticket'")
    assert php("profile", *LAB_OPTS).returncode == 0  # dry-run changes nothing
    assert sql("select rights from glpi_profilerights where profiles_id=9 and name='computer'") == "13"
    assert php("profile", *LAB_OPTS, "--apply").returncode == 0
    assert sql("select name,rights from glpi_profilerights where profiles_id=9 and rights>0") == "computer\t1"
    assert php("profile", "--profile=9", "--profile-name=wrong", "--apply").returncode == 1


@lab
def test_lab_functional_probe_pass_and_fail():
    subprocess.run(["docker", "restart", "ninf-glpi-maintenance-gateway"], check=True, capture_output=True)  # re-read rotated secret
    time.sleep(8)
    ids = json.loads((LAB / "ids.json").read_text())
    tokens = {k: (LAB / f).read_text().strip() for k, f in (("app", "app_token"), ("user", "user_token"), ("bearer", "bearer"))}

    def docker_run(container, script, payload):
        p = subprocess.run(["docker", "exec", "-i", container, "python3", "-c", script],
                           input=json.dumps(payload), capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, p.stderr
        return json.loads(p.stdout)

    kw = dict(containers=["ness-glpi-lab-hub"], tokens=tokens, glpi_url="http://ness-glpi-lab-glpi/apirest.php",
              gateway_url="http://ninf-glpi-maintenance-gateway:8000",
              allowed=ids["1"]["Computer"], denied=[ids["5"]["Computer"] + 100, ids["5"]["Computer"] + 200])  # e5 itself is on the lab allowlist on purpose; the matrix covers it
    assert probe.run(docker_run, **kw) == []
    # Negative control: a client allowed from the Hub's IP makes the same credential work -> probe must FAIL.
    hub_ip = subprocess.run(
        ["docker", "inspect", "ness-glpi-lab-hub", "--format", '{{(index .NetworkSettings.Networks "glpi-lab_ninf-net").IPAddress}}'],
        capture_output=True, text=True).stdout.strip()
    app = php("apiclient", "--client-name=t23-hub", f"--ip={hub_ip}", *LAB_OPTS, "--apply").stdout
    try:
        findings = probe.run(docker_run, **{**kw, "tokens": {**tokens, "app": app}})
        assert any("initSession with gateway -> 200" in f for f in findings)
    finally:
        sql("delete from glpi_apiclients where name='t23-hub'")
