import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "zsd", Path(__file__).parents[1] / "scripts/zabbix-site-dependencies.py"
)
zsd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zsd)

FG = [{"name": "FortiGate by SNMP"}]
G1, G2 = "[ A ] [ Um ]", "[ A ] [ Dois ]"


def host(hid, name, groups, tpl=()):
    return {
        "hostid": hid,
        "host": name,
        "hostgroups": [{"name": g} for g in groups],
        "parentTemplates": list(tpl),
    }


HOSTS = [
    host("1", "fw1", [G1], FG),
    host("2", "srv1", [G1 + " [ Rack ]"]),
    host("3", "fw2a", [G2], FG),
    host("4", "fw2b", [G2], FG),
    host("5", "srv2", [G2]),
    host("6", "solto", ["[ A ] [ Vazio ]", "Linux servers"]),
]


class Fake:
    def __init__(self):
        self.hosts = HOSTS
        self.trig = {}
        self.next = 100
        for hid, desc, deps in [
            ("1", "FortiGate: Unavailable by ICMP ping", []),
            ("2", "Linux: High CPU", ["77"]),
            ("2", "Linux: Zabbix agent is not available", []),
            ("5", "Disk full", []),
            ("5", "No data from host", []),
        ]:
            self.add(hid, desc, deps)

    def add(self, hid, desc, deps, tags=()):
        tid = str(self.next)
        self.next += 1
        self.trig[tid] = {
            "hostid": hid,
            "description": desc,
            "deps": list(deps),
            "tags": list(tags),
        }
        return tid

    def by_desc(self, desc):
        return next(k for k, v in self.trig.items() if v["description"] == desc)

    def call(self, method, p):
        if method == "host.get":
            if "filter" in p and "host" in p["filter"]:
                return [h for h in self.hosts if h["host"] in p["filter"]["host"]]
            return self.hosts
        if method == "trigger.get":
            out = []
            for tid, t in self.trig.items():
                if "hostids" in p and t["hostid"] not in p["hostids"]:
                    continue
                if "triggerids" in p and tid not in p["triggerids"]:
                    continue
                if "tags" in p and not any(
                    x["tag"] == p["tags"][0]["tag"]
                    and x["value"] == p["tags"][0]["value"]
                    for x in t["tags"]
                ):
                    continue
                out.append(
                    {
                        "triggerid": tid,
                        "description": t["description"],
                        "dependencies": [{"triggerid": d} for d in t["deps"]],
                    }
                )
            return out
        if method == "trigger.update":
            assert len(p) <= zsd.BATCH
            for u in p:
                self.trig[u["triggerid"]]["deps"] = [
                    d["triggerid"] for d in u["dependencies"]
                ]
            return {}
        if method == "trigger.create":
            c = p[0]
            gw = c["expression"].split("/")[1]
            hid = next(h["hostid"] for h in self.hosts if h["host"] == gw)
            return {"triggerids": [self.add(hid, c["description"], [], c["tags"])]}
        if method == "trigger.delete":
            for tid in p:
                del self.trig[tid]
            return {}
        raise AssertionError(method)


def topo(tmp_path):
    path = tmp_path / "t.json"
    path.write_text(json.dumps(zsd.build_topology(HOSTS)))
    return str(path)


def test_generate_maps_sites_and_nested_groups():
    sites = {s["site"]: s for s in zsd.generate(Fake())["sites"]}
    assert sites[G1]["gateways"] == ["fw1"] and sites[G1]["hosts"] == ["srv1"]
    assert sites[G2]["gateways"] == ["fw2a", "fw2b"] and sites[G2]["hosts"] == ["srv2"]
    assert sites["[ A ] [ Vazio ]"]["gateways"] == []
    assert all(s["revisado"] is False for s in sites.values())


def test_plan_two_gateways_includes_aggregate():
    site = {"site": G2, "gateways": ["fw2a", "fw2b"], "hosts": ["srv2"]}
    plan = zsd.plan_site(Fake(), site)
    assert plan["create"]["description"] == zsd.AGG_DESC
    assert (
        plan["create"]["expression"]
        == "last(/fw2a/icmpping)=0 and last(/fw2b/icmpping)=0"
    )
    assert plan["triggers"] == 1


def test_apply_keeps_existing_deps_and_is_idempotent(tmp_path):
    api = Fake()
    t = topo(tmp_path)
    rec = zsd.main(
        ["apply", "--all", "--topology", t, "--record-dir", str(tmp_path)], api
    )
    fw = api.by_desc("FortiGate: Unavailable by ICMP ping")
    agg = api.by_desc(zsd.AGG_DESC)
    assert api.trig[api.by_desc("Linux: High CPU")]["deps"] == ["77", fw]
    assert api.trig[api.by_desc("Disk full")]["deps"] == [agg]
    for d in ("Linux: Zabbix agent is not available", "No data from host"):
        assert api.trig[api.by_desc(d)]["deps"] == []
    before = json.dumps(api.trig, sort_keys=True)
    (tmp_path / "x").mkdir()  # mesmo segundo geraria o mesmo nome de registro
    rec2 = zsd.main(
        ["apply", "--all", "--topology", t, "--record-dir", str(tmp_path / "x")], api
    )
    assert json.dumps(api.trig, sort_keys=True) == before
    assert all(
        e["pairs"] == [] and e["created_triggerid"] is None
        for e in json.load(open(rec2))
    )
    assert {e["site"] for e in json.load(open(rec))} == {G1, G2}


def test_rollback_removes_only_recorded_pairs(tmp_path):
    api = Fake()
    rec = zsd.main(
        ["apply", "--all", "--topology", topo(tmp_path), "--record-dir", str(tmp_path)],
        api,
    )
    cpu = api.by_desc("Linux: High CPU")
    api.trig[cpu]["deps"].append("88")
    zsd.main(["rollback", "--record", rec], api)
    assert api.trig[cpu]["deps"] == ["77", "88"]
    assert api.trig[api.by_desc("Disk full")]["deps"] == []
    assert all(t["description"] != zsd.AGG_DESC for t in api.trig.values())


def test_site_without_gateways_yields_nothing(tmp_path, capsys):
    path = tmp_path / "t.json"
    path.write_text(
        json.dumps(
            {"sites": [{"site": "[ X ] [ Y ]", "gateways": [], "hosts": ["srv1"]}]}
        )
    )
    zsd.main(["plan", "--topology", str(path)], Fake())
    assert capsys.readouterr().out == ""
