"""Reconciliação Hub -> GLPI com um GLPI falso em memória (pulado sem NINF_TEST_PG_URL)."""

import itertools

import pytest
from sqlalchemy import select

from app.models import Customer, TeamMember, User, UserRole
from app.services import glpi_team_sync as sync

pytestmark = pytest.mark.asyncio


class FakeGlpi:
    def __init__(self):
        self.n = itertools.count(100)
        self.down = False
        self.writes = 0
        self.t = {k: [] for k in ("Profile", "User", "Group", "Group_User", "Profile_User", "RuleTicket", "RuleCriteria", "RuleAction")}
        self.t["Profile"] = [{"id": 6, "name": sync.P_NESS}, {"id": 14, "name": sync.P_EXT}]

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
        cav = (await s.execute(select(Customer).where(Customer.key == "cavan"))).scalar_one()
        users = [
            User(email="ana@ness.com.br", hashed_password="x", full_name="Ana", role=UserRole.noc, is_oncall=True),
            User(email="elid@cavan.com", hashed_password="x", full_name="Elid", role=UserRole.cliente, tenant_id="cavan"),
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
    assert [(r["profiles_id"], r["entities_id"], r["is_recursive"]) for r in rows] == [(14, 8, 0)]


async def test_manual_glpi_extra_member_is_removed_and_reported(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    grp = next(x for x in g.t["Group"] if x["name"] == "ness · Cavan")
    g.t["Group_User"].append({"id": 999, "users_id": 55, "groups_id": grp["id"]})
    assert any(d.startswith("REMOVE") for d in await _diff(people_maker, g))
    assert all(r["id"] != 999 for r in g.t["Group_User"])


async def test_deactivated_user_removed_from_groups_and_disabled_not_deleted(people_maker):
    await _seed(people_maker)
    g = FakeGlpi()
    await _diff(people_maker, g)
    async with people_maker() as s:
        u = (await s.execute(select(User).where(User.email == "ana@ness.com.br"))).scalar_one()
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
