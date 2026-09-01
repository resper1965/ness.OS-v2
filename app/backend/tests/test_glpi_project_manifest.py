from pathlib import Path

import pytest

from app.integrations.glpi_project_manifest import render_project_report, validate_project_manifest


MANIFEST = Path(__file__).parents[3] / "config/glpi/ness-os-foundation-v1.yaml"


def mutate(tmp_path, replacement):
    path = tmp_path / "manifest.yaml"
    path.write_text(MANIFEST.read_text(encoding="utf-8").replace(*replacement), encoding="utf-8")
    return path


def test_current_manifest_has_required_projects_and_parent_references():
    report = validate_project_manifest(MANIFEST)
    assert report["project_count"] == 5
    assert report["work_package_count"] == 13


def test_duplicate_project_codes_rejected(tmp_path):
    path = mutate(tmp_path, ("code: PRJ-GLPI-001\n    name:", "code: PRJ-NESSOS-001\n    name:"))
    with pytest.raises(ValueError, match="duplicate project codes"):
        validate_project_manifest(path)


def test_unknown_parent_rejected(tmp_path):
    path = mutate(tmp_path, ("parent_project: PRJ-GLPI-001", "parent_project: PRJ-MISSING-001"))
    with pytest.raises(ValueError, match="unknown project"):
        validate_project_manifest(path)


def test_project_parent_cycle_rejected(tmp_path):
    source = MANIFEST.read_text(encoding="utf-8") + "\n  # no mutation: cycle fixture is explicit\n"
    source = source.replace("code: PRJ-NESSOS-001\n    name:", "code: PRJ-NESSOS-001\n    parent_project: PRJ-GLPI-001\n    name:")
    source = source.replace("code: PRJ-GLPI-001\n    name:", "code: PRJ-GLPI-001\n    parent_project: PRJ-NESSOS-001\n    name:")
    path = tmp_path / "manifest.yaml"
    path.write_text(source, encoding="utf-8")
    with pytest.raises(ValueError, match="parent cycle"):
        validate_project_manifest(path)


def test_report_is_dry_run_only_and_does_not_modify_manifest(tmp_path):
    before = MANIFEST.read_bytes()
    assert render_project_report(MANIFEST) == "projects=5 work_packages=13 action=dry-run-only"
    assert MANIFEST.read_bytes() == before
