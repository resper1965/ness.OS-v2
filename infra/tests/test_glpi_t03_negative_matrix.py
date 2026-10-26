"""T03 negative matrix against the synthetic lab (infra/tests/glpi-lab/lab.sh up).

Skipped without GLPI_LAB_URL (gateway, e.g. http://127.0.0.1:18000). Every path
must deny entity 5 data; entity 1 read is the positive control. The lab also
approves the entity-5 Computer ID in the allowlist, so the entity check on the
server side is what is under test, not the allowlist.
"""

import ipaddress
import json
import os
import subprocess
from pathlib import Path

import httpx
import pytest

URL = os.getenv("GLPI_LAB_URL")
pytestmark = pytest.mark.skipif(not URL, reason="GLPI_LAB_URL not set")

LAB = Path(os.getenv("GLPI_LAB_DIR", "/tmp/opencode/glpi-lab"))
IDS = json.loads((LAB / "ids.json").read_text()) if URL else {}
SECRETS = [(LAB / n).read_text() for n in ("app_token", "user_token", "bearer")] if URL else []
AUTH = {"Authorization": f"Bearer {SECRETS[2]}"} if URL else {}
E1, E5 = IDS.get("1", {}), IDS.get("5", {})
SUBNET = ipaddress.ip_network("172.30.250.0/28")

def call(method, path, **kw):
    headers = {**AUTH, **kw.pop("headers", {})}
    with httpx.Client(base_url=URL, follow_redirects=False, timeout=15) as c:
        return c.request(method, path, headers=headers, **kw)

def assert_denied(r):
    assert r.status_code >= 400, (r.request.url, r.status_code)
    assert "-e5" not in r.text and '"entities_id":5' not in r.text.replace(" ", "")

def assert_no_entity5_data(r):
    assert "-e5" not in r.text and '"entities_id":5' not in r.text.replace(" ", "")

def docker(*args):
    return subprocess.run(["docker", *args], check=False, capture_output=True, text=True, timeout=60)

def test_entity_1_asset_read_allowed():
    r = call("GET", f"/v1/computers/{E1['Computer']}")
    assert r.status_code == 200
    assert r.json() == {"id": E1["Computer"], "name": "lab-computer-e1", "entities_id": 1}

@pytest.mark.parametrize("path", ["/changeActiveEntities", "/v1/changeActiveEntities", "/v1/entities/5"])
def test_switch_to_descendant_entity_denied(path):
    assert_denied(call("POST", path, json={"entities_id": 5, "is_recursive": True}))

def test_entities_id_all_denied():
    assert_denied(call("GET", f"/v1/computers/{E1['Computer']}?entities_id=all&is_recursive=1"))
    for path in (
        f"/v1/computers/{E5['Computer']}?entities_id=all&is_recursive=1",
        "/v1/computers?entities_id=all",
    ):
        assert_denied(call("GET", path, headers={"X-GLPI-Entity": "all"}))

def test_computer_idor_denied():
    assert_denied(call("GET", f"/v1/computers/{E5['Computer']}"))
    assert_denied(call("GET", f"/v1/computers/{E5['Computer'] + 100}"))

def test_ticket_idor_denied():
    for path in (f"/v1/tickets/{E5['Ticket']}", f"/Ticket/{E5['Ticket']}", f"/v1/tickets/{E1['Ticket']}"):
        assert_denied(call("GET", path))

def test_document_attachment_idor_denied():
    for path in (
        f"/v1/documents/{E5['Document']}",
        f"/v1/documents/{E5['Document']}/download",
        f"/Document/{E5['Document']}?alt=media",
    ):
        assert_denied(call("GET", path, headers={"Accept": "application/octet-stream"}))

def test_search_other_entity_empty():
    r = call("GET", "/v1/search/Computer?criteria[0][field]=80&criteria[0][searchtype]=equals&criteria[0][value]=5")
    assert_no_entity5_data(r)
    assert r.status_code >= 400 or not r.json()

def test_export_denied():
    for path in ("/v1/computers?export=csv", "/v1/search/Computer?export_all=1&forcedisplay[0]=1"):
        assert_denied(call("GET", path))

def test_batch_denied():
    ids = [E1["Computer"], E5["Computer"]]
    assert_denied(call("POST", "/v1/batch", json=[{"method": "GET", "path": f"/Computer/{i}"} for i in ids]))
    assert_denied(call("GET", f"/v1/computers/{ids[0]},{ids[1]}"))
    assert_denied(call("PUT", "/v1/computers", json={"input": [{"id": i} for i in ids]}))

@pytest.mark.parametrize("sep", ["%2F", "%252F"])
def test_encoded_path_traversal_denied(sep):
    for prefix in ("/v1/computers", "/Computer"):
        assert_denied(call("GET", f"{prefix}/{E1['Computer']}{sep}..{sep}{E5['Computer']}"))

def test_nested_foreign_id_denied():
    c = E1["Computer"]
    for path in (
        f"/v1/computers/{c}/tickets/{E5['Ticket']}",
        f"/v1/computers/{c}/Document_Item/{E5['Document']}",
        f"/v1/computers/{c}?with_tickets=1&ticket_id={E5['Ticket']}",
    ):
        assert_denied(call("GET", path))

def test_reused_session_denied():
    # A live upstream session minted with the gateway's own credentials, replayed by a client.
    mint = (
        "import json,urllib.request as u;"
        "r=lambda n:open('/run/secrets/'+n).read().strip();"
        "q=u.Request('http://glpi-maintenance-private/apirest.php/initSession',"
        "headers={'App-Token':r('glpi_app_token'),'Authorization':'user_token '+r('glpi_user_token')});"
        "print(json.load(u.urlopen(q))['session_token'])"
    )
    out = docker("exec", "ninf-glpi-maintenance-gateway", "python", "-c", mint)
    assert out.returncode == 0
    session = out.stdout.strip()
    SECRETS.append(session)
    h = {"Session-Token": session, "App-Token": SECRETS[0]}
    assert_denied(call("GET", f"/v1/computers/{E5['Computer']}", headers=h))
    assert call("GET", f"/v1/computers/{E1['Computer']}", headers=h).json()["entities_id"] == 1

def test_upstream_token_never_returned():
    seen = [
        call("GET", f"/v1/computers/{E1['Computer']}"),
        call("GET", f"/v1/computers/{E5['Computer']}"),
        call("GET", f"/v1/computers/{E1['Computer']}", headers={"Authorization": "Bearer wrong"}),
        call("GET", "/v1/initSession"),
        call("GET", "/apirest.php/initSession"),
    ]
    for r in seen:
        blob = r.text + str(r.headers)
        assert "session_token" not in blob.lower()
        assert not any(s and s in blob for s in SECRETS)

def test_direct_upstream_from_hub_network_denied():
    # The Hub keeps its native route to GLPI (ADR 0020), so the maintenance credential must be useless from there.
    probe = (
        "import os,urllib.request as u,urllib.error\n"
        "for h in ('ness-glpi-lab-glpi','glpi-maintenance-private'):\n"
        "    q=u.Request(f'http://{h}/apirest.php/initSession',headers={'App-Token':os.environ['A'],"
        "'Authorization':'user_token '+os.environ['U'],'X-Forwarded-For':'172.30.250.3'})\n"
        "    try: u.urlopen(q,timeout=3); print('LOGGED_IN',h)\n"
        "    except Exception: pass\n"
    )
    out = docker("exec", "-e", f"A={SECRETS[0]}", "-e", f"U={SECRETS[1]}", "ness-glpi-lab-hub", "python", "-c", probe)
    assert out.returncode == 0 and out.stdout.strip() == ""

def test_exclusive_subnet_has_no_collision():
    names = docker("network", "ls", "-q").stdout.split()
    nets = json.loads(docker("network", "inspect", *names).stdout)
    owners = [
        n["Name"]
        for n in nets
        for c in (n["IPAM"]["Config"] or [])
        if "Subnet" in c and ipaddress.ip_network(c["Subnet"], strict=False).overlaps(SUBNET)
    ]
    assert owners == ["glpi-lab_glpi-maintenance-private"]
    private = next(n for n in nets if n["Name"] == owners[0])
    assert private["Internal"] is True
    assert not any(
        ipaddress.ip_address(c["IPv4Address"].split("/")[0]) not in SUBNET
        for c in private["Containers"].values()
    )
