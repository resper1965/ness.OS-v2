"""Hub -> GLPI: o Hub é o cadastro único de pessoas e equipes; o GLPI é reconciliado.

Lê tudo do GLPI primeiro (GLPI fora do ar = nada gravado), depois grava só a diferença.
Só mexe no que o Hub gerencia: grupos "ness · …", regras "ness-hub …" e usuários que
existem no Hub. Nunca apaga usuário; usuário inativo no Hub é desativado no GLPI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select, text

from app.models import Customer, TeamMember, User, UserRole

logger = logging.getLogger("nessops.glpi_team_sync")

PREFIX = "ness · "
ONCALL = PREFIX + "Plantão"
RULE_PREFIX = "ness-hub entidade "
P_NESS, P_EXT = "Technician", "Técnico externo"
_LOCK = 7_422_001  # chave do advisory lock da reconciliação


@dataclass(frozen=True)
class Person:
    login: str  # parte local do e-mail: é como o GLPI já identifica quem entra por SSO
    email: str
    name: str
    external: bool
    active: bool
    entity_id: int | None = None  # só externo: a entidade do único cliente dele


@dataclass
class Desired:
    people: dict[str, Person] = field(default_factory=dict)
    # nome do grupo -> (entidade, recursivo, logins)
    groups: dict[str, tuple[int, bool, set[str]]] = field(default_factory=dict)
    rules: dict[int, str] = field(default_factory=dict)  # entidade -> nome do grupo
    errors: list[str] = field(default_factory=list)


async def desired_state(session) -> Desired:
    d = Desired()
    users = (await session.execute(select(User))).scalars().all()
    customers = {
        c.id: c
        for c in (
            await session.execute(select(Customer).where(Customer.active.is_(True)))
        ).scalars()
        if c.glpi_entity_id is not None
    }
    by_login: dict[str, User] = {}
    for u in users:
        login = u.email.split("@")[0].lower()
        if login in by_login:
            d.errors.append(f"login repetido: {login}")
            continue
        by_login[login] = u
    teams: dict[int, set[int]] = {}
    for m in (await session.execute(select(TeamMember))).scalars():
        teams.setdefault(m.customer_id, set()).add(m.user_id)
    login_of = {u.id: lg for lg, u in by_login.items()}
    for login, u in by_login.items():
        ext = u.role == UserRole.cliente
        own = [
            c
            for c in customers.values()
            if (c.key or "").lower() == (u.tenant_id or "").lower()
        ]
        d.people[login] = Person(
            login,
            u.email,
            u.full_name or login,
            ext,
            u.is_active,
            own[0].glpi_entity_id if ext and own else None,
        )
    for c in customers.values():
        name = f"{PREFIX}{c.display_name}"
        if name == ONCALL:
            d.errors.append(f"cliente {c.key}: nome reservado ao plantão")
            continue
        members = {
            login_of[uid]
            for uid in teams.get(c.id, ())
            if uid in login_of and d.people[login_of[uid]].active
        }
        d.groups[name] = (c.glpi_entity_id, False, members)
        d.rules[c.glpi_entity_id] = name
    d.groups[ONCALL] = (
        0,
        True,
        {
            lg
            for lg, u in by_login.items()
            if u.is_oncall and u.is_active and u.role != UserRole.cliente
        },
    )
    return d


async def _read(glpi) -> dict:
    profiles = {p["name"]: int(p["id"]) for p in await glpi.list_items("Profile")}
    for needed in (P_NESS, P_EXT):
        if needed not in profiles:
            raise RuntimeError(f"Perfil {needed!r} ausente no GLPI (rode a base fixa)")
    rules = [
        r
        for r in await glpi.list_items("RuleTicket")
        if str(r["name"]).startswith(RULE_PREFIX)
    ]
    for r in rules:
        r["_actions"] = await glpi.list_items(f"RuleTicket/{r['id']}/RuleAction")
        r["_criteria"] = await glpi.list_items(f"RuleTicket/{r['id']}/RuleCriteria")
    return {
        "profiles": profiles,
        "users": {u["name"].lower(): u for u in await glpi.list_items("User")},
        "groups": await glpi.list_items("Group"),
        "group_users": await glpi.list_items("Group_User"),
        "profile_users": await glpi.list_items("Profile_User"),
        "rules": rules,
    }


async def reconcile(glpi, d: Desired, apply: bool) -> list[str]:
    """Diferenças no formato "CREATE user x"; grava só com apply=True. Idempotente."""
    if d.errors:  # ambiguidade de login: nada é gravado até o cadastro ser corrigido
        return [f"ERRO {e}" for e in d.errors]
    cur = await _read(glpi)
    diff: list[str] = []

    async def do(desc: str, coro_fn):
        diff.append(desc)
        return await coro_fn() if apply else None

    # --- grupos
    gid: dict[str, int | None] = {}
    for name, (eid, rec, _) in d.groups.items():
        hit = next(
            (
                g
                for g in cur["groups"]
                if g["name"] == name and int(g["entities_id"]) == eid
            ),
            None,
        )
        if hit:
            gid[name] = int(hit["id"])
            if int(hit.get("is_recursive", 0)) != int(rec):
                await do(
                    f"FIX group {name} recursão",
                    lambda hit=hit, rec=rec: glpi.update_item(
                        "Group", hit["id"], {"is_recursive": int(rec)}
                    ),
                )
            continue
        gid[name] = await do(
            f"CREATE group {name}",
            lambda name=name, eid=eid, rec=rec: glpi.create_item(
                "Group",
                {
                    "name": name,
                    "entities_id": eid,
                    "is_recursive": int(rec),
                    "is_assign": 1,
                    "is_notify": 0,
                    "comment": "Gerido pelo ness.OS Hub.",
                },
            ),
        )

    # --- usuários: só quem está em alguma equipe (ativo) ou foi desativado no Hub
    in_team = {lg for _, _, ms in d.groups.values() for lg in ms}
    uid: dict[str, int | None] = {}
    for login, p in d.people.items():
        row = cur["users"].get(login)
        if p.active and login in in_team:
            if row is None:
                uid[login] = await do(
                    f"CREATE user {login}",
                    lambda p=p: glpi.create_item(
                        "User",
                        {
                            "name": p.login,
                            "realname": p.name,
                            "authtype": 3,
                            "is_active": 1,
                            "entities_id": 0,
                            "_useremails": {"-1": p.email},
                        },
                    ),
                )
            else:
                uid[login] = int(row["id"])
                if (row.get("realname") or "") != p.name:
                    await do(
                        f"RENAME user {login}",
                        lambda r=row, p=p: glpi.update_item(
                            "User", r["id"], {"realname": p.name}
                        ),
                    )
                if not int(row["is_active"]):
                    await do(
                        f"ENABLE user {login}",
                        lambda r=row: glpi.update_item(
                            "User", r["id"], {"is_active": 1}
                        ),
                    )
        elif row is not None:
            uid[login] = int(row["id"])
            if not p.active and int(row["is_active"]):
                await do(
                    f"DISABLE user {login}",
                    lambda r=row: glpi.update_item("User", r["id"], {"is_active": 0}),
                )

    # --- membros dos grupos gerenciados (extras são removidos)
    managed = {
        int(g["id"]): (g["name"], int(g["entities_id"]))
        for g in cur["groups"]
        if str(g["name"]).startswith(PREFIX)
    }
    have: dict[tuple[str, int], dict[int, int]] = {}
    for gu in cur["group_users"]:
        if int(gu["groups_id"]) in managed:
            have.setdefault(managed[int(gu["groups_id"])], {})[int(gu["users_id"])] = (
                int(gu["id"])
            )
    id_login = {v: k for k, v in uid.items() if v}
    for name, (eid, _, members) in d.groups.items():
        cur_members = have.get((name, eid), {})
        for login in sorted(members):
            if uid.get(login) is None or uid[login] not in cur_members:
                await do(
                    f"ADD {login}→{name}",
                    lambda login=login, name=name: glpi.create_item(
                        "Group_User", {"users_id": uid[login], "groups_id": gid[name]}
                    ),
                )
        for user_id, link_id in cur_members.items():
            if id_login.get(user_id) not in members:
                who = id_login.get(user_id) or f"#{user_id}"
                await do(
                    f"REMOVE {who}→{name}",
                    lambda link_id=link_id: glpi.delete_item("Group_User", link_id),
                )
    wanted = {(n, e) for n, (e, _, _) in d.groups.items()}
    for (gname, geid), cur_members in have.items():
        if (
            gname,
            geid,
        ) not in wanted:  # grupo de cliente que saiu ou mudou de entidade
            for user_id, link_id in cur_members.items():
                await do(
                    f"REMOVE #{user_id}→{gname}",
                    lambda link_id=link_id: glpi.delete_item("Group_User", link_id),
                )

    # --- perfis: para quem o Hub cadastra, Technician e Técnico externo batem exatamente
    # com o desejado (perfil, entidade, recursão). Outros perfis (Super-Admin etc.) ficam.
    ext_pid, ness_pid = cur["profiles"][P_EXT], cur["profiles"][P_NESS]
    managed_pids = {ext_pid, ness_pid}
    want_of: dict[str, tuple[int, int, int]] = {}
    for login in sorted(in_team):
        p = d.people[login]
        if p.external and p.entity_id is None:
            diff.append(f"ERRO {login}: externo sem cliente ativo")
            continue
        want_of[login] = (
            (ext_pid, p.entity_id or 0, 0) if p.external else (ness_pid, 0, 1)
        )
    for login, want in want_of.items():
        person_id = uid.get(login)
        have_rows = {
            (
                int(r["profiles_id"]),
                int(r["entities_id"]),
                int(r.get("is_recursive", 0)),
            )
            for r in cur["profile_users"]
            if person_id and int(r["users_id"]) == person_id
        }
        if want not in have_rows:
            await do(
                f"PROFILE {login}→{'externo' if want[0] == ext_pid else 'técnico'}",
                lambda person_id=person_id, want=want: glpi.create_item(
                    "Profile_User",
                    {
                        "users_id": person_id,
                        "profiles_id": want[0],
                        "entities_id": want[1],
                        "is_recursive": want[2],
                    },
                ),
            )
    for r in cur["profile_users"]:
        owner = id_login.get(int(r["users_id"]))
        if not owner or int(r["profiles_id"]) not in managed_pids:
            continue
        key = (
            int(r["profiles_id"]),
            int(r["entities_id"]),
            int(r.get("is_recursive", 0)),
        )
        if want_of.get(owner) != key:
            kind = "externo" if key[0] == ext_pid else "técnico"
            await do(
                f"UNPROFILE {owner}←{kind}",
                lambda r=r: glpi.delete_item("Profile_User", r["id"]),
            )

    # --- regra: entidade -> grupo
    rules = {
        int(c["pattern"]): r
        for r in cur["rules"]
        for c in r["_criteria"]
        if c["criteria"] == "entities_id"
    }
    for eid, name in d.rules.items():
        r = rules.get(eid)
        if r is None:

            async def make(eid=eid, name=name):
                rid = await glpi.create_item(
                    "RuleTicket",
                    {
                        "name": f"{RULE_PREFIX}{eid}",
                        "sub_type": "RuleTicket",
                        "match": "AND",
                        "condition": 1,
                        "is_active": 1,
                        "entities_id": 0,
                        "is_recursive": 1,
                    },
                )
                await glpi.create_item(
                    "RuleCriteria",
                    {
                        "rules_id": rid,
                        "criteria": "entities_id",
                        "condition": 0,
                        "pattern": eid,
                    },
                )
                await glpi.create_item(
                    "RuleAction",
                    {
                        "rules_id": rid,
                        "action_type": "assign",
                        "field": "_groups_id_assign",
                        "value": gid[name],
                    },
                )

            await do(f"CREATE rule entidade {eid}→{name}", make)
            continue
        act = next(
            (a for a in r["_actions"] if a["field"] == "_groups_id_assign"), None
        )
        if gid.get(name) and (act is None or int(act["value"]) != gid[name]):
            if act:
                await do(
                    f"FIX rule entidade {eid}→{name}",
                    lambda a=act, name=name: glpi.update_item(
                        "RuleAction", a["id"], {"value": gid[name]}
                    ),
                )
            else:
                await do(
                    f"FIX rule entidade {eid}→{name}",
                    lambda r=r, name=name: glpi.create_item(
                        "RuleAction",
                        {
                            "rules_id": r["id"],
                            "action_type": "assign",
                            "field": "_groups_id_assign",
                            "value": gid[name],
                        },
                    ),
                )
        if not int(r["is_active"]):
            await do(
                f"ENABLE rule entidade {eid}",
                lambda r=r: glpi.update_item("RuleTicket", r["id"], {"is_active": 1}),
            )
    for eid, r in rules.items():
        if eid not in d.rules:
            await do(
                f"DISABLE rule entidade {eid}",
                lambda r=r: glpi.update_item("RuleTicket", r["id"], {"is_active": 0}),
            )
    return diff


async def run_sync(apply: bool) -> list[str]:
    """Ponto de entrada do worker e da API. Sem credencial própria, não faz nada."""
    from app.config import get_settings
    from app.database import SessionLocal
    from app.integrations.glpi import GLPIClient

    token = get_settings().glpi_team_user_token
    if not token:
        raise RuntimeError("NINF_GLPI_TEAM_USER_TOKEN não configurado")
    glpi = GLPIClient(user_token=token)
    try:
        async with SessionLocal() as session:
            # Uma reconciliação por vez entre todos os workers (o lock cai ao fechar a conexão).
            got = (
                await session.execute(
                    text("SELECT pg_try_advisory_lock(:k)"), {"k": _LOCK}
                )
            ).scalar_one()
            if not got:
                return ["JA_EM_EXECUCAO"]
            try:
                await glpi.use_all_entities()
                d = await desired_state(session)
                diff = await reconcile(glpi, d, apply)
            finally:
                await session.execute(
                    text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK}
                )
    finally:
        await glpi.kill_session()
    if apply and diff:
        logger.warning("glpi_team_sync aplicou %d mudanças: %s", len(diff), diff)
    return diff
