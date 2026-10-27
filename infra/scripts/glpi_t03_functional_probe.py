#!/usr/bin/env python3
"""T03 functional probe for production (read-only, stdlib only).

Replaces the network probe: ninf-glpi stays on ninf-net, so the proof is behavioural.
  A) from each Hub container, initSession with the maintenance user_token must be refused
     (HTTP 400/401/403) for every App-Token that container can use: its own
     NINF_GLPI_APP_TOKEN plus the gateway's plus none at all
     (an API client with an empty App-Token accepts logins without the header).
  B) from ninf-api, the gateway answers 200 only for the allowed entity-1 Computer, 404 otherwise.
Run as root on the host (secrets are 0600 root). Tokens go to the containers by stdin and
never to argv, stdout or logs. Exit 0 = PASS, 1 = FAIL.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

DENIED = {400, 401, 403}

_SESSION = r"""
import json, os, sys, urllib.request as u, urllib.error as e
d = json.load(sys.stdin)
base = d.get("glpi_url") or os.environ["NINF_GLPI_URL"]
apps = {"none": "", **d["app_tokens"]}  # GLPI accepts a missing App-Token when a client with an empty one matches the IP
if d.get("env_token", True) and os.environ.get("NINF_GLPI_APP_TOKEN"):
    apps["container-env"] = os.environ["NINF_GLPI_APP_TOKEN"]
out = {}
for label, app in apps.items():
    h = {"Authorization": "user_token " + d["user_token"]}
    if app:
        h["App-Token"] = app
    q = u.Request(base + "/initSession", headers=h)
    try:
        r = u.urlopen(q, timeout=8)
        out[label] = r.status
        k = u.Request(base + "/killSession", headers={**({"App-Token": app} if app else {}), "Session-Token": json.load(r)["session_token"]})
        u.urlopen(k, timeout=8).read()
    except e.HTTPError as x:
        out[label] = x.code
    except Exception as x:
        out[label] = type(x).__name__
print(json.dumps(out))
"""

_GATEWAY = r"""
import json, sys, urllib.request as u, urllib.error as e
d = json.load(sys.stdin)
def call(path, bearer=True, method="GET"):
    q = u.Request(d["base"] + path, method=method, data=b"" if method == "POST" else None,
                  headers={"Authorization": "Bearer " + d["bearer"]} if bearer else {})
    try:
        r = u.urlopen(q, timeout=8)
        return r.status, r.read().decode()
    except e.HTTPError as x:
        return x.code, ""
    except Exception as x:
        return type(x).__name__, ""
a = d["allowed"]
cases = {"live": call("/live", False), f"allowed:{a}": call(f"/v1/computers/{a}"),
         "allowed+query": call(f"/v1/computers/{a}?entities_id=all"),
         "allowed-no-bearer": call(f"/v1/computers/{a}", False), "allowed-post": call(f"/v1/computers/{a}", method="POST")}
for i in d["denied"]:
    cases[f"denied:{i}"] = call(f"/v1/computers/{i}")
out = {}
for k, (s, body) in cases.items():
    out[k] = {"status": s}
    if k.startswith("allowed:") and s == 200:
        try:
            j = json.loads(body)
            out[k]["keys"] = sorted(j)
            out[k]["entities_id"] = j.get("entities_id")
            out[k]["id"] = j.get("id")
        except ValueError:
            out[k]["keys"] = ["<invalid json>"]
print(json.dumps(out))
"""


def judge_session(container: str, result: dict) -> list[str]:
    """Findings for one container's initSession results (label -> status)."""
    if not result:
        return [f"{container}: no App-Token tried"]
    return [
        f"{container}: initSession with {label} -> {status} (expected one of {sorted(DENIED)})"
        for label, status in sorted(result.items())
        if status not in DENIED
    ]


def judge_gateway(allowed: int, denied: list[int], result: dict) -> list[str]:
    expect = {"live": {200}, "allowed+query": {404}, "allowed-no-bearer": {401}, "allowed-post": {404, 405}}
    expect[f"allowed:{allowed}"] = {200}
    expect.update({f"denied:{i}": {404} for i in denied})
    findings = [
        f"gateway {case}: {result.get(case, {}).get('status')} (expected {sorted(want)})"
        for case, want in expect.items()
        if result.get(case, {}).get("status") not in want
    ]
    ok = result.get(f"allowed:{allowed}", {})
    if ok.get("status") == 200 and (
        ok.get("keys") != ["entities_id", "id", "name"] or ok.get("entities_id") != 1 or ok.get("id") != allowed
    ):
        findings.append(f"gateway allowed:{allowed}: unexpected body shape/entity {ok}")
    return findings


def run(runner, *, containers, tokens, glpi_url, gateway_url, allowed, denied, env_token=True) -> list[str]:
    """runner(container, script, payload_dict) -> parsed JSON. Returns findings (empty = PASS)."""
    findings = []
    for c in containers:
        payload = {"user_token": tokens["user"], "app_tokens": {"gateway": tokens["app"]}, "glpi_url": glpi_url, "env_token": env_token}
        findings += judge_session(c, runner(c, _SESSION, payload))
    gw = runner(
        containers[0], _GATEWAY, {"base": gateway_url, "bearer": tokens["bearer"], "allowed": allowed, "denied": denied}
    )
    return findings + judge_gateway(allowed, denied, gw)


def docker_runner(docker: list[str]):
    def runner(container, script, payload):
        p = subprocess.run(
            [*docker, "exec", "-i", container, "python3", "-c", script],
            input=json.dumps(payload), capture_output=True, text=True, timeout=120,
        )
        if p.returncode:
            raise SystemExit(f"{container}: probe failed to run (rc={p.returncode}): {p.stderr.strip()[-200:]}")
        return json.loads(p.stdout)

    return runner


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--secrets-dir", default="/etc/ness-os/glpi-maintenance")
    ap.add_argument("--docker", default="docker", help='e.g. "sudo -n docker"')
    ap.add_argument("--containers", nargs="+", default=["ninf-api", "ninf-worker-alerts"])
    ap.add_argument("--skip-env-token", action="store_true",
                    help="do not try the container's own NINF_GLPI_APP_TOKEN (Hub client 2: valid from its IP by design; accepted risk, see runbook)")
    ap.add_argument("--glpi-url", help="default: NINF_GLPI_URL inside each container")
    ap.add_argument("--gateway-url", default="http://ninf-glpi-maintenance-gateway:8000")
    ap.add_argument("--allowed-id", type=int, required=True, help="approved entity-1 Computer ID")
    ap.add_argument("--denied-id", type=int, nargs="+", required=True, help="IDs outside the allowlist (e.g. a child-entity Computer)")
    a = ap.parse_args(argv)
    d = Path(a.secrets_dir)
    tokens = {k: (d / f).read_text().strip() for k, f in (("app", "app_token"), ("user", "user_token"), ("bearer", "bearer"))}
    findings = run(
        docker_runner(a.docker.split()), containers=a.containers, tokens=tokens, glpi_url=a.glpi_url,
        gateway_url=a.gateway_url, allowed=a.allowed_id, denied=a.denied_id, env_token=not a.skip_env_token,
    )
    print("PASS_FUNCTIONAL_PROBE" if not findings else "FAIL_FUNCTIONAL_PROBE")
    for f in findings:
        print(" -", f)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
