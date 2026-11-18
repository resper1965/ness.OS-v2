#!/usr/bin/env python3
"""Dependência de triggers por site no Zabbix 7.0: queda do gateway suprime alertas do site.

generate  -> grava a topologia (site, gateways, hosts) para revisão humana
plan      -> mostra o que seria criado (padrão, só leitura)
apply     -> cria as dependências e grava um registro para rollback
rollback  -> remove exatamente os pares do registro e apaga triggers agregados
"""

import argparse
import datetime
import json
import os
import re
import sys
import urllib.request

SITE_RE = re.compile(r"^(\[[^\]]+\] \[[^\]]+\])(?: \[[^\]]+\])*$")
AVAIL_RE = re.compile(r"unavailable by icmp|agent is not available|no data", re.I)
GW_TRIGGER_RE = re.compile(r"unavailable by icmp", re.I)
AGG_DESC = "ness.OS: todos os gateways do site fora"
TAG = "ness_os_dep"
BATCH = 200


class Api:
    def __init__(self, url, token):
        self.url, self.token, self.id = url, token, 0

    def call(self, method, params):
        self.id += 1
        body = json.dumps(
            {"jsonrpc": "2.0", "method": method, "params": params, "id": self.id}
        ).encode()
        req = urllib.request.Request(
            self.url,
            body,
            {
                "Content-Type": "application/json-rpc",
                "Authorization": f"Bearer {self.token}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.load(r)
        if "error" in resp:
            raise RuntimeError(f"{method}: {resp['error']}")
        return resp["result"]


def read_token(path):
    with open(path) as f:
        for line in f:
            k, _, v = line.strip().partition("=")
            if k.removeprefix("export ").strip() == "ZABBIX_API_TOKEN":
                return v.strip().strip("'\"")
    sys.exit(f"ZABBIX_API_TOKEN ausente em {path}")


def build_topology(hosts):
    sites = {}
    for h in hosts:
        names = {
            m.group(1)
            for g in h.get("hostgroups", [])
            if (m := SITE_RE.match(g["name"]))
        }
        is_gw = any("FortiGate" in t["name"] for t in h.get("parentTemplates", []))
        for s in names:
            entry = sites.setdefault(s, {"gateways": set(), "hosts": set()})
            entry["gateways" if is_gw else "hosts"].add(h["host"])
    return {
        "sites": [
            {
                "site": s,
                "gateways": sorted(v["gateways"]),
                "hosts": sorted(v["hosts"]),
                "revisado": False,
            }
            for s, v in sorted(sites.items())
        ]
    }


def generate(api):
    return build_topology(
        api.call(
            "host.get",
            {
                "output": ["hostid", "host"],
                "filter": {"status": 0},
                "selectHostGroups": ["name"],
                "selectParentTemplates": ["name"],
            },
        )
    )


def hostids(api, names):
    if not names:
        return {}
    res = api.call(
        "host.get", {"output": ["hostid", "host"], "filter": {"host": names}}
    )
    return {h["host"]: h["hostid"] for h in res}


def triggers(api, **params):
    return api.call(
        "trigger.get",
        {
            "output": ["triggerid", "description"],
            "selectDependencies": ["triggerid"],
            **params,
        },
    )


def deps_of(t):
    return [d["triggerid"] for d in t.get("dependencies", [])]


def resolve_parent(api, site):
    """Retorna (parent_id ou None, params de criação ou None)."""
    gws = site["gateways"]
    ids = hostids(api, gws)
    if len(gws) == 1:
        found = [
            t
            for t in triggers(api, hostids=[ids[gws[0]]], filter={"status": 0})
            if GW_TRIGGER_RE.search(t["description"])
        ]
        if not found:
            raise RuntimeError(f"{site['site']}: gateway sem trigger ICMP")
        return sorted(found, key=lambda t: int(t["triggerid"]))[0]["triggerid"], None
    agg = triggers(
        api,
        hostids=list(ids.values()),
        tags=[{"tag": TAG, "value": site["site"], "operator": 1}],
    )
    if agg:
        return agg[0]["triggerid"], None
    return None, {
        "description": AGG_DESC,
        "expression": " and ".join(f"last(/{g}/icmpping)=0" for g in gws),
        "priority": 4,
        "tags": [{"tag": TAG, "value": site["site"]}],
    }


def dependents(api, site, parent):
    """Triggers habilitados dos hosts não-gateway que ainda não dependem do pai."""
    ids = list(hostids(api, site["hosts"]).values())
    if not ids:
        return []
    return [
        t
        for t in triggers(api, hostids=ids, filter={"status": 0})
        if not AVAIL_RE.search(t["description"]) and parent not in deps_of(t)
    ]


def plan_site(api, site):
    parent, create = resolve_parent(api, site)
    todo = dependents(api, site, parent)
    return {
        "site": site["site"],
        "parent_triggerid": parent,
        "create": create,
        "triggers": len(todo),
    }


def update_deps(api, new_deps):
    items = [
        {"triggerid": tid, "dependencies": [{"triggerid": d} for d in deps]}
        for tid, deps in new_deps.items()
    ]
    for i in range(0, len(items), BATCH):
        api.call("trigger.update", items[i : i + BATCH])


def apply_site(api, site):
    parent, create = resolve_parent(api, site)
    created = None
    if create:
        created = parent = api.call("trigger.create", [create])["triggerids"][0]
    todo = dependents(api, site, parent)
    update_deps(api, {t["triggerid"]: deps_of(t) + [parent] for t in todo})
    return {
        "site": site["site"],
        "parent_triggerid": parent,
        "created_triggerid": created,
        "pairs": [[t["triggerid"], parent] for t in todo],
    }


def rollback(api, record, site=None):
    entries = [e for e in record if site in (None, e["site"])]
    remove = {}
    for e in entries:
        for tid, pid in e["pairs"]:
            remove.setdefault(tid, set()).add(pid)
    if remove:
        current = triggers(api, triggerids=list(remove))
        update_deps(
            api,
            {
                t["triggerid"]: [
                    d for d in deps_of(t) if d not in remove[t["triggerid"]]
                ]
                for t in current
            },
        )
    created = [e["created_triggerid"] for e in entries if e["created_triggerid"]]
    if created:
        api.call("trigger.delete", created)
    return len(remove), len(created)


def selected(topology, args):
    sites = [s for s in topology["sites"] if s["gateways"]]
    if args.site:
        sites = [s for s in sites if s["site"] == args.site]
        if not sites:
            sys.exit(f"site sem gateway ou inexistente: {args.site}")
    return sites


def main(argv=None, api=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "action",
        nargs="?",
        default="plan",
        choices=["generate", "plan", "apply", "rollback"],
    )
    p.add_argument("--site")
    p.add_argument("--all", action="store_true")
    p.add_argument("--out", default="infra/zabbix/topologia-sites.json")
    p.add_argument("--topology", default="infra/zabbix/topologia-sites.json")
    p.add_argument("--record")
    p.add_argument("--record-dir", default="infra/zabbix")
    p.add_argument(
        "--url",
        default=os.environ.get("ZBX_URL", "http://127.0.0.1:8080/api_jsonrpc.php"),
    )
    a = p.parse_args(argv)
    if a.action == "apply" and not (a.site or a.all):
        p.error("apply exige --site S ou --all")
    if a.action == "rollback" and not a.record:
        p.error("rollback exige --record FILE")
    if api is None:
        token_file = os.environ.get(
            "ZBX_TOKEN_FILE", "/etc/ness-os/zabbix-cutover-bootstrap.env"
        )
        api = Api(a.url, read_token(token_file))

    if a.action == "generate":
        with open(a.out, "w") as f:
            json.dump(generate(api), f, ensure_ascii=False, indent=2)
        print(f"topologia gravada em {a.out}")
        return
    if a.action == "rollback":
        with open(a.record) as f:
            n, c = rollback(api, json.load(f), a.site)
        print(f"rollback: {n} triggers revertidos, {c} agregados apagados")
        return
    with open(a.topology) as f:
        sites = selected(json.load(f), a)
    if a.action == "plan":
        for s in sites:
            print(json.dumps(plan_site(api, s), ensure_ascii=False))
        return
    record = [apply_site(api, s) for s in sites]
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    path = os.path.join(a.record_dir, f"aplicado-{stamp}.json")
    with open(path, "w") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(
        f"{sum(len(r['pairs']) for r in record)} dependências criadas; registro em {path}"
    )
    return path


if __name__ == "__main__":
    main()
