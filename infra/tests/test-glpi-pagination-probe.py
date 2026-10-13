"""The read-only GLPI probe must not call a malformed page successful."""

import importlib.util
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "scripts" / "glpi_pagination_probe.py"
spec = importlib.util.spec_from_file_location("glpi_pagination_probe", source)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_accepts_two_matching_single_item_pages():
    assert probe._valid_page([{"id": 1}], "0-0/103", 0)
    assert probe._valid_page([{"id": 2}], "items 1-1/103", 1)


def test_rejects_missing_or_inconsistent_pagination():
    assert not probe._valid_page([{"id": 1}], None, 0)
    assert not probe._valid_page([{"id": 1}], "1-1/103", 0)
    assert not probe._valid_page([], "0-0/103", 0)
