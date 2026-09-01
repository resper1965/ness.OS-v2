import os
import urllib.request
import json
import ssl

url = "https://zabbix.ness.com.br/api_jsonrpc.php"
token = os.environ["ZABBIX_API_TOKEN"]

headers = {"Content-Type": "application/json-rpc"}

payload = {
    "jsonrpc": "2.0",
    "method": "user.get",
    "params": {
        "output": ["userid", "username", "name", "surname"],
        "selectMedias": ["mediaid", "mediatypeid", "sendto", "active", "severity", "period"]
    },
    "auth": token,
    "id": 1
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
try:
    with urllib.request.urlopen(req, context=ctx) as response:
        res = json.loads(response.read().decode('utf-8'))
        if "error" in res:
            print("Zabbix API Error:", res["error"])
        else:
            users = res.get("result", [])
            print(f"Retrieved {len(users)} users from Zabbix:")
            for u in users:
                medias = u.get("medias", [])
                print(f"User: {u['username']} (Name: {u['name']}, Surname: {u['surname']}), Medias: {medias}")
except Exception as e:
    print("Request Failed:", e)
