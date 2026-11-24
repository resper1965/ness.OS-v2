"""Reconciliação Hub -> GLPI com um GLPI falso em memória (pulado sem NINF_TEST_PG_URL)."""

import itertools

import pytest
from sqlalchemy import delete, select

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
