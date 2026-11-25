"""Reconciliação Hub -> GLPI com um GLPI falso em memória (pulado sem NINF_TEST_PG_URL)."""

import itertools

import pytest
from sqlalchemy import delete, select, update

from app.models import Customer, TeamMember, User, UserRole
from app.services import glpi_team_sync as sync

pytestmark = pytest.mark.asyncio


class FakeGlpi:
    def __init__(self):
        self.n = itertools.count(100)
        self.down = False
        self.writes = 0
        self.t = {
            k: []
            for k in (
                "Profile",
                "User",
                "Group",
                "Group_User",
                "Profile_User",
                "RuleTicket",
                "RuleCriteria",
                "RuleAction",
            )
        }
        self.t["Profile"] = [
            {"id": 6, "name": sync.P_NESS},
            {"id": 14, "name": sync.P_EXT},
        ]

    async def list_items(self, path):
        if self.down:
            raise RuntimeError("GLPI fora")
        if path.startswith("RuleTicket/"):
            rid, kind = int(path.split("/")[1]), path.split("/")[2]
            return [x for x in self.t[kind] if x["rules_id"] == rid]
        return list(self.t[path])

    async def create_item(self, itemtype, data):
        self.writes += 1
        row = {"id": next(self.n), "is_active": 1, **data}
        self.t[itemtype].append(row)
        return row["id"]

    async def update_item(self, itemtype, item_id, data):
        self.writes += 1
        next(r for r in self.t[itemtype] if r["id"] == item_id).update(data)

    async def delete_item(self, itemtype, item_id):
        self.writes += 1
        self.t[itemtype] = [r for r in self.t[itemtype] if r["id"] != item_id]


async def _seed(maker):
    async with maker() as s:
        cav = (
            await s.execute(select(Customer).where(Customer.key == "cavan"))
        ).scalar_one()
        users = [
            User(
                email="ana@ness.com.br",
                hashed_password="x",
                full_name="Ana",
                role=UserRole.noc,
                is_oncall=True,
            ),
            User(
                email="elid@cavan.com",
                hashed_password="x",
                full_name="Elid",
                role=UserRole.cliente,
                tenant_id="cavan",
            ),
        ]
        s.add_all(users)
        await s.flush()
        s.add_all(TeamMember(customer_id=cav.id, user_id=u.id) for u in users)
        await s.commit()
        return cav, users


async def _diff(maker, glpi, apply=True):
    async with maker() as s:
        return await sync.reconcile(glpi, await sync.desired_state(s), apply)


async def test_new_member_creates_user_and_membership(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    diff = await _diff(people_maker, g)
    assert "CREATE user ana" in diff and "ADD ana→ness · Cavan" in diff
    assert any(r["name"] == "ness-hub entidade 8" for r in g.t["RuleTicket"])


async def test_external_gets_external_profile_only_on_own_entity(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    ext = next(u for u in g.t["User"] if u["name"] == "elid")
    rows = [r for r in g.t["Profile_User"] if r["users_id"] == ext["id"]]
    assert [(r["profiles_id"], r["entities_id"], r["is_recursive"]) for r in rows] == [
        (14, 8, 0)
    ]


async def test_manual_glpi_extra_member_is_removed_and_reported(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    grp = next(x for x in g.t["Group"] if x["name"] == "ness · Cavan")
    g.t["Group_User"].append({"id": 999, "users_id": 55, "groups_id": grp["id"]})
    assert any(d.startswith("REMOVE") for d in await _diff(people_maker, g))
    assert all(r["id"] != 999 for r in g.t["Group_User"])


async def test_deactivated_user_removed_from_groups_and_disabled_not_deleted(
    people_maker,
):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    async with people_maker() as s:
        u = (
            await s.execute(select(User).where(User.email == "ana@ness.com.br"))
        ).scalar_one()
        u.is_active = False
        await s.commit()
    diff = await _diff(people_maker, g)
    assert "DISABLE user ana" in diff and any(d.startswith("REMOVE ana") for d in diff)
    assert next(u for u in g.t["User"] if u["name"] == "ana")["is_active"] == 0


async def test_second_run_is_noop(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    before = g.writes
    assert await _diff(people_maker, g) == []
    assert g.writes == before


async def test_glpi_down_raises_and_changes_nothing(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    g.down = True
    with pytest.raises(RuntimeError):
        await _diff(people_maker, g)
    assert g.writes == 0


async def test_dry_run_writes_nothing(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    assert await _diff(people_maker, g, apply=False)
    assert g.writes == 0


async def test_login_collision_is_blocked_by_the_database(people_maker):
    from sqlalchemy.exc import IntegrityError

    await _seed(people_maker)
    async with people_maker() as s:
        s.add(User(email="ANA@outro.com", hashed_password="x", role=UserRole.noc))
        with pytest.raises(IntegrityError):
            await s.commit()


async def test_desired_state_with_colliding_logins_aborts_without_writes(people_maker):
    g = FakeGlpi()
    d = sync.Desired(errors=["login repetido: ana"])
    assert (await sync.reconcile(g, d, True))[0].startswith("ERRO") and g.writes == 0


async def test_internal_removed_from_all_teams_loses_technician_profile(people_maker):
    cav, users = await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    ana = next(u for u in g.t["User"] if u["name"] == "ana")
    assert any(r["users_id"] == ana["id"] for r in g.t["Profile_User"])
    async with people_maker() as s:
        u = (
            await s.execute(select(User).where(User.email == "ana@ness.com.br"))
        ).scalar_one()
        u.is_oncall = False
        await s.execute(delete(TeamMember).where(TeamMember.user_id == u.id))
        await s.commit()
    diff = await _diff(people_maker, g)
    assert "UNPROFILE ana←técnico" in diff
    assert not any(r["users_id"] == ana["id"] for r in g.t["Profile_User"])


async def test_entity_change_moves_members_to_the_new_group(people_maker):
    cav, _ = await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    async with people_maker() as s:
        c = await s.get(Customer, cav.id)
        c.glpi_entity_id = 77
        await s.commit()
    diff = await _diff(people_maker, g)
    assert "CREATE group ness · Cavan" in diff and "ADD ana→ness · Cavan" in diff


async def test_name_change_updates_glpi_realname(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    async with people_maker() as s:
        u = (
            await s.execute(select(User).where(User.email == "ana@ness.com.br"))
        ).scalar_one()
        u.full_name = "Ana Souza"
        await s.commit()
    assert "RENAME user ana" in await _diff(people_maker, g)
    assert next(u for u in g.t["User"] if u["name"] == "ana")["realname"] == "Ana Souza"


async def test_external_with_root_technician_loses_it(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    ext = next(u for u in g.t["User"] if u["name"] == "elid")
    g.t["Profile_User"].append(
        {
            "id": 900,
            "users_id": ext["id"],
            "profiles_id": 6,
            "entities_id": 0,
            "is_recursive": 1,
        }
    )
    assert "UNPROFILE elid←técnico" in await _diff(people_maker, g)
    assert [
        (r["profiles_id"], r["entities_id"])
        for r in g.t["Profile_User"]
        if r["users_id"] == ext["id"]
    ] == [(14, 8)]


async def test_external_profile_with_wrong_recursion_is_replaced(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    ext = next(u for u in g.t["User"] if u["name"] == "elid")
    next(r for r in g.t["Profile_User"] if r["users_id"] == ext["id"])[
        "is_recursive"
    ] = 1
    await _diff(people_maker, g)
    rows = [r for r in g.t["Profile_User"] if r["users_id"] == ext["id"]]
    assert [(r["profiles_id"], r["entities_id"], r["is_recursive"]) for r in rows] == [
        (14, 8, 0)
    ]


async def test_advisory_lock_blocks_a_second_reconciliation(people_maker, monkeypatch):
    from sqlalchemy import text

    from app import database

    monkeypatch.setattr(database, "SessionLocal", people_maker)
    monkeypatch.setenv("NINF_GLPI_TEAM_USER_TOKEN", "x")
    from app.config import get_settings

    get_settings.cache_clear()
    async with people_maker() as holder:
        await holder.execute(text("SELECT pg_advisory_lock(:k)"), {"k": sync._LOCK})
        try:
            assert await sync.run_sync(apply=True) == ["JA_EM_EXECUCAO"]
        finally:
            await holder.execute(
                text("SELECT pg_advisory_unlock(:k)"), {"k": sync._LOCK}
            )
    get_settings.cache_clear()


async def test_group_recursion_is_reconciled(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    plantao = next(x for x in g.t["Group"] if x["name"] == sync.ONCALL)
    plantao["is_recursive"] = 0
    assert f"FIX group {sync.ONCALL} recursão" in await _diff(people_maker, g)
    assert plantao["is_recursive"] == 1


async def test_run_sync_selects_all_entities_before_reading(people_maker, monkeypatch):
    from app import database
    from app.config import get_settings
    from app.integrations import glpi as glpi_mod

    calls = []

    class Spy(FakeGlpi):
        def __init__(self, **kw):
            super().__init__()

        async def use_all_entities(self):
            calls.append("all")
            return set(range(0, 200))

        async def list_items(self, path):
            calls.append(path)
            return await super().list_items(path)

        async def kill_session(self):
            return True

    monkeypatch.setattr(glpi_mod, "GLPIClient", Spy)
    monkeypatch.setattr(database, "SessionLocal", people_maker)
    monkeypatch.setenv("NINF_GLPI_TEAM_USER_TOKEN", "x")
    get_settings.cache_clear()
    await sync.run_sync(apply=False)
    get_settings.cache_clear()
    assert calls[0] == "all" and "Profile" in calls


async def test_customer_named_like_oncall_group_aborts(people_maker):
    cav, _ = await _seed(people_maker)
    async with people_maker() as s:
        c = await s.get(Customer, cav.id)
        c.display_name = "Plantão"
        await s.commit()
    g = FakeGlpi()
    diff = await _diff(people_maker, g)
    assert diff[0].startswith("ERRO") and g.writes == 0


async def test_run_sync_aborts_when_token_cannot_see_a_customer_entity(
    people_maker, monkeypatch
):
    from app import database
    from app.config import get_settings
    from app.integrations import glpi as glpi_mod

    class Spy(FakeGlpi):
        def __init__(self, **kw):
            super().__init__()

        async def use_all_entities(self):
            return {0}

        async def kill_session(self):
            return True

    await _seed(people_maker)
    monkeypatch.setattr(glpi_mod, "GLPIClient", Spy)
    monkeypatch.setattr(database, "SessionLocal", people_maker)
    monkeypatch.setenv("NINF_GLPI_TEAM_USER_TOKEN", "x")
    get_settings.cache_clear()
    out = await sync.run_sync(apply=True)
    get_settings.cache_clear()
    assert out and out[0].startswith("ERRO entidades")


async def test_rule_scope_is_reconciled(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    rule = next(r for r in g.t["RuleTicket"] if r["name"].startswith(sync.RULE_PREFIX))
    rule["is_recursive"] = 0
    assert any("escopo" in x for x in await _diff(people_maker, g))
    assert rule["is_recursive"] == 1


async def test_rule_criterion_operator_is_reconciled(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    c = next(x for x in g.t["RuleCriteria"] if x["criteria"] == "entities_id")
    c["condition"] = 1
    assert any("critério" in x for x in await _diff(people_maker, g))
    assert c["condition"] == 0


async def test_managed_rule_without_entity_criterion_is_disabled(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    g.t["RuleCriteria"] = []
    diff = await _diff(people_maker, g)
    assert any(x.startswith("DISABLE rule ness-hub") for x in diff)
    assert any(x.startswith("CREATE rule") for x in diff)


async def test_rule_with_surplus_criterion_or_action_is_replaced(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    rid = next(
        r["id"] for r in g.t["RuleTicket"] if r["name"].startswith(sync.RULE_PREFIX)
    )
    g.t["RuleCriteria"].append(
        {"id": 901, "rules_id": rid, "criteria": "name", "condition": 0, "pattern": "x"}
    )
    diff = await _diff(people_maker, g)
    assert any(x.startswith("DISABLE rule") for x in diff) and any(
        x.startswith("CREATE rule") for x in diff
    )
    assert await _diff(people_maker, g) == []


async def test_obsolete_disabled_rule_causes_no_writes(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    async with people_maker() as s:
        await s.execute(update(Customer).values(active=False))
        await s.commit()
    await _diff(people_maker, g)
    assert await _diff(people_maker, g) == []


async def test_rule_with_zero_execution_mask_is_repaired(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    rule = next(r for r in g.t["RuleTicket"] if r["name"].startswith(sync.RULE_PREFIX))
    rule["condition"] = 0
    assert any("escopo" in x for x in await _diff(people_maker, g))
    assert rule["condition"] == 1


async def test_rule_with_non_numeric_entity_pattern_does_not_abort(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    next(c for c in g.t["RuleCriteria"] if c["criteria"] == "entities_id")[
        "pattern"
    ] = "abc"
    diff = await _diff(people_maker, g)
    assert any(x.startswith("DISABLE rule") for x in diff)


async def test_group_assign_flag_and_action_type_are_repaired(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    grp = next(x for x in g.t["Group"] if x["name"] == sync.ONCALL)
    grp["is_assign"] = 0
    assert f"FIX group {sync.ONCALL} atribuição" in await _diff(people_maker, g)
    assert grp["is_assign"] == 1
    next(a for a in g.t["RuleAction"])["action_type"] = "append"
    diff = await _diff(people_maker, g)
    assert any(x.startswith("DISABLE rule") for x in diff) and any(
        x.startswith("CREATE rule") for x in diff
    )


async def test_adopted_user_gets_sso_authtype(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    u = next(x for x in g.t["User"] if x["name"] == "ana")
    u["authtype"] = 1
    assert "SSO user ana" in await _diff(people_maker, g)
    assert u["authtype"] == 3


async def test_rule_with_empty_group_value_is_replaced_not_crashing(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    next(a for a in g.t["RuleAction"])["value"] = ""
    diff = await _diff(people_maker, g)
    assert any(x.startswith("DISABLE rule") for x in diff) and any(
        x.startswith("CREATE rule") for x in diff
    )


async def test_stale_profile_is_revoked_before_new_one_is_granted(people_maker):
    cav, _ = await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    async with people_maker() as s:
        other = (
            await s.execute(select(Customer).where(Customer.key == "tbe"))
        ).scalar_one()
        u = (
            (await s.execute(select(User).where(User.role == UserRole.cliente)))
            .scalars()
            .first()
        )
        u.tenant_id = other.key
        await s.execute(delete(TeamMember).where(TeamMember.user_id == u.id))
        s.add(TeamMember(customer_id=other.id, user_id=u.id))
        await s.commit()
    diff = await _diff(people_maker, g)
    i = next(i for i, x in enumerate(diff) if x.startswith("UNPROFILE"))
    j = next(i for i, x in enumerate(diff) if x.startswith("PROFILE"))
    assert i < j


async def test_malformed_rule_is_disabled_before_replacement_is_created(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    g.t["RuleCriteria"] = []
    diff = await _diff(people_maker, g)
    assert next(i for i, x in enumerate(diff) if x.startswith("DISABLE rule")) < next(
        i for i, x in enumerate(diff) if x.startswith("CREATE rule")
    )


async def test_customer_name_too_long_for_glpi_group_aborts(people_maker):
    cav, _ = await _seed(people_maker)
    async with people_maker() as s:
        c = await s.get(Customer, cav.id)
        c.display_name = "x" * 255
        await s.commit()
    g = FakeGlpi()
    diff = await _diff(people_maker, g)
    assert diff[0].startswith("ERRO") and g.writes == 0


async def test_existing_privileged_glpi_account_is_not_adopted(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    g.t["User"].append(
        {"id": 500, "name": "ana", "realname": "Root", "authtype": 1, "is_active": 1}
    )
    g.t["Profile_User"].append(
        {
            "id": 800,
            "users_id": 500,
            "profiles_id": 4,
            "entities_id": 0,
            "is_recursive": 1,
        }
    )
    diff = await _diff(people_maker, g)
    assert not any("ana" in x for x in diff)
    assert next(u for u in g.t["User"] if u["id"] == 500)["authtype"] == 1


async def test_protected_account_keeps_group_membership(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    g.t["User"].append(
        {"id": 500, "name": "ana", "realname": "Root", "authtype": 1, "is_active": 1}
    )
    g.t["Profile_User"].append(
        {
            "id": 800,
            "users_id": 500,
            "profiles_id": 4,
            "entities_id": 0,
            "is_recursive": 1,
        }
    )
    gr = next(x for x in g.t["Group"] if x["name"].startswith(sync.PREFIX))
    g.t["Group_User"].append({"id": 900, "users_id": 500, "groups_id": gr["id"]})
    diff = await _diff(people_maker, g)
    assert not any(x.startswith("REMOVE") and "500" in x for x in diff)
    assert any(r["id"] == 900 for r in g.t["Group_User"])


async def test_duplicate_glpi_login_aborts_without_writes(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    for i in (501, 502):
        g.t["User"].append(
            {"id": i, "name": "Ana", "realname": "x", "authtype": 1, "is_active": 1}
        )
    diff = await _diff(people_maker, g)
    assert diff[0].startswith("ERRO login repetido") and g.writes == 0


async def test_no_team_registered_writes_nothing(people_maker):
    g = FakeGlpi()
    d = sync.Desired()
    d.groups["ness · X"] = (8, False, set())
    out = await sync.reconcile(g, d, True)
    assert out[0].startswith("ERRO nenhuma equipe") and g.writes == 0
