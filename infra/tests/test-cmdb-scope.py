"""Exercise the pure scope guard without opening database/API connections."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


def guard():
    path = Path(__file__).parents[2] / "app/backend/app/integrations/cmdb_sync.py"
    tree = ast.parse(path.read_text())
    functions = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "scoped_hosts"
    ]
    namespace = {}
    exec(  # noqa: S102 - compile only the trusted repository function, without imports
        compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"),
        namespace,
    )
    return namespace.get("scoped_hosts", lambda *_: None)


def identity_guard():
    path = Path(__file__).parents[2] / "app/backend/app/integrations/cmdb_sync.py"
    tree = ast.parse(path.read_text())
    functions = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "assert_existing_asset_identity"
    ]
    namespace = {}
    exec(  # noqa: S102 - compile only the trusted repository function, without imports
        compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"),
        namespace,
    )
    return namespace["assert_existing_asset_identity"]


def test_scope_preserves_explicit_three_hosts():
    assert guard()(["10983", "10984", "10987"]) == ["10983", "10984", "10987"]


@pytest.mark.parametrize(
    "ids", [[], ["1"] * 2, [str(i) for i in range(1, 7)], ["x"], ["0"]]
)
def test_invalid_scope_fails_closed(ids):
    with pytest.raises(ValueError):
        guard()(ids)


def test_unscoped_legacy_operation_is_preserved():
    assert guard()(None) is None


def test_existing_asset_identity_accepts_same_glpi_reference():
    existing = SimpleNamespace(
        customer_id="alupar",
        tags={"glpi_entity_id": 1, "glpi_itemtype": "Computer", "glpi_item_id": 80},
    )
    incoming = {
        "customer_id": "alupar",
        "tags": {
            "glpi_entity_id": 1,
            "glpi_itemtype": "Computer",
            "glpi_item_id": "80",
        },
    }
    identity_guard()(existing, incoming)


@pytest.mark.parametrize(
    ("customer", "entity", "itemtype", "item_id"),
    [
        ("other", 1, "Computer", 80),
        ("alupar", 5, "Computer", 80),
        ("alupar", 1, "NetworkEquipment", 80),
        ("alupar", 1, "Computer", 81),
    ],
)
def test_existing_asset_identity_rejects_rebinding(customer, entity, itemtype, item_id):
    existing = SimpleNamespace(
        customer_id="alupar",
        tags={"glpi_entity_id": 1, "glpi_itemtype": "Computer", "glpi_item_id": 80},
    )
    incoming = {
        "customer_id": customer,
        "tags": {
            "glpi_entity_id": entity,
            "glpi_itemtype": itemtype,
            "glpi_item_id": item_id,
        },
    }
    with pytest.raises(ValueError, match="Existing asset identity changed"):
        identity_guard()(existing, incoming)


def test_reconcile_calls_identity_guard_for_existing_assets():
    path = Path(__file__).parents[2] / "app/backend/app/integrations/cmdb_sync.py"
    tree = ast.parse(path.read_text())
    reconcile = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "reconcile"
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "assert_existing_asset_identity"
        for node in ast.walk(reconcile)
    )
