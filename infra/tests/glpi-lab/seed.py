"""Seed synthetic entities 1 (parent) and 5 (child) with Computer/Ticket/Document each.
Runs inside the GLPI container (localhost API client). Prints ids as JSON."""
import base64
import json
import os
import urllib.request

B = "http://127.0.0.1/apirest.php"

def call(path, method="GET", body=None, headers=None):
    req = urllib.request.Request(
        B + path, method=method, headers=headers or {},
        data=json.dumps(body).encode() if body is not None else None,
    )
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path}: {e.code} {e.read()[:300]!r}")

auth = base64.b64encode(b"glpi:glpi").decode()
def login():
    tok = call("/initSession", headers={"Authorization": "Basic " + auth})["session_token"]
    return {"Session-Token": tok}

H = login()

def add(itemtype, **fields):
    return call("/" + itemtype, "POST", {"input": fields}, H)["id"]

ent = {1: add("Entity", name="lab-parent", entities_id=0)}
for n in (2, 3, 4):
    assert add("Entity", name=f"lab-filler-{n}", entities_id=0) == n
H = login()  # the session caches visible entities; refresh before using the new parent
ent[5] = add("Entity", name="lab-child", entities_id=1)
H = login()
assert ent == {1: 1, 5: 5}, ent

out = {"entities": [1, 5]}
for e in (1, 5):
    out[e] = {
        "Computer": add("Computer", name=f"lab-computer-e{e}", entities_id=e),
        "Ticket": add("Ticket", name=f"lab-ticket-e{e}", content="synthetic", entities_id=e),
        "Document": add("Document", name=f"lab-document-e{e}", entities_id=e),
    }

prof = add("Profile", name="lab-maintenance-ro", interface="central")
user = add("User", name="svc_lab_maintenance", password="Lab-only-pass-1!", password2="Lab-only-pass-1!")
add("Profile_User", users_id=user, profiles_id=prof, entities_id=1, is_recursive=1)  # recursive: entity 5 is reachable natively, so the gateway check is what denies it
# App-Token is stored encrypted, so create the API client through GLPI itself.
add("APIClient", name="lab maintenance gateway", is_active=1, app_token=os.environ["APP_TOKEN"],
    ipv4_range_start=os.environ["GATEWAY_IP"], ipv4_range_end=os.environ["GATEWAY_IP"])
out.update(profile=prof, user=user)
call("/killSession", headers=H)
print(json.dumps(out))
