"""Dry-run validation for the GLPI project/work-package manifest.

This module is deliberately local-only: it never creates a GLPI client or
performs network/production writes.
"""

from pathlib import Path
from typing import Any


REQUIRED_PROJECT_FIELDS = ("code", "name", "class", "manager_role")


def _sections(path: Path) -> dict[str, list[dict[str, str]]]:
    sections: dict[str, list[dict[str, str]]] = {
        "project_pilots": [],
        "work_packages": [],
    }
    section: str | None = None
    current: dict[str, str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(" ") and line.endswith(":"):
            section = line[:-1] if line[:-1] in sections else None
            current = None
        elif section and line.startswith("  - "):
            current = {}
            sections[section].append(current)
            item = line[4:]
            if ":" in item:
                key, value = item.split(":", 1)
                current[key.strip()] = value.strip()
        elif (
            section and current is not None and line.startswith("    ") and ":" in line
        ):
            key, value = line.strip().split(":", 1)
            current[key.strip()] = value.strip()
    return sections


def validate_project_manifest(path: Path) -> dict[str, Any]:
    """Return a report, raising ``ValueError`` for invalid project structure."""
    sections = _sections(path)
    projects = sections["project_pilots"]
    packages = sections["work_packages"]
    errors: list[str] = []
    codes = [p.get("code", "") for p in projects]
    duplicate_codes = sorted({code for code in codes if code and codes.count(code) > 1})
    if duplicate_codes:
        errors.append(f"duplicate project codes: {', '.join(duplicate_codes)}")
    for index, project in enumerate(projects, 1):
        missing = [field for field in REQUIRED_PROJECT_FIELDS if not project.get(field)]
        if missing:
            errors.append(f"project {index} missing: {', '.join(missing)}")
    project_codes = set(codes)
    for package in packages:
        parent = package.get("parent_project", "")
        if parent and parent not in project_codes:
            errors.append(
                f"work package {package.get('code', '<unknown>')} references unknown project {parent}"
            )

    # Optional project parent links are checked as a graph, while preserving
    # compatibility with the current flat manifest.
    parents = {
        p["code"]: p["parent_project"]
        for p in projects
        if p.get("code") and p.get("parent_project")
    }
    for start in parents:
        seen: set[str] = set()
        node = start
        while node in parents:
            if node in seen:
                errors.append(f"project parent cycle involving {node}")
                break
            seen.add(node)
            node = parents[node]
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "projects": projects,
        "work_packages": packages,
        "project_count": len(projects),
        "work_package_count": len(packages),
    }


def render_project_report(path: Path) -> str:
    """Render a deterministic human-readable dry-run report."""
    report = validate_project_manifest(path)
    return (
        f"projects={report['project_count']} work_packages={report['work_package_count']} "
        "action=dry-run-only"
    )
