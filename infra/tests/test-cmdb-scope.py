"""Exercise the pure scope guard without opening database/API connections."""
import ast
from pathlib import Path

import pytest


def guard():
    path = Path(__file__).parents[2] / "app/backend/app/integrations/cmdb_sync.py"
    tree = ast.parse(path.read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "scoped_hosts"]
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
    return namespace.get("scoped_hosts", lambda *_: None)


def test_scope_preserves_explicit_three_hosts():
    assert guard()(["10983", "10984", "10987"]) == ["10983", "10984", "10987"]


@pytest.mark.parametrize("ids", [[], ["1"] * 2, [str(i) for i in range(1, 7)], ["x"], ["0"]])
def test_invalid_scope_fails_closed(ids):
    with pytest.raises(ValueError):
        guard()(ids)


def test_unscoped_legacy_operation_is_preserved():
    assert guard()(None) is None
