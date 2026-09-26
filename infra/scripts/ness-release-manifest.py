#!/usr/bin/env python3
"""Create deterministic local and production release evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SENSITIVE_KEY = re.compile(
    r"(?:secret|password|passwd|token|credential|private.?key|access.?key|api.?key|auth)",
    re.IGNORECASE,
)
VERSION_KEYS = ("zabbix_version", "mariadb_version", "php_version", "wazuh_version")
DEPLOYED_NAMES = {
    "app/docker-compose.yml",
    "app/Caddyfile",
    "app/backend/postgresql.conf",
    "infra/psono/docker-compose.yml",
    "infra/psono/Caddyfile",
    "infra/psono/branding/custom.css",
    "infra/psono/branding/index.html",
    "infra/psono/branding/language-default.js",
    "infra/psono/branding/portal-index.html",
    "infra/psono/branding/service-worker-load.js",
    "infra/psono/branding/service-worker.js",
    "infra/scripts/aiops-nightly-backup.sh",
    "infra/scripts/aiops-deployment-backup.sh",
    "infra/scripts/ness-object-storage-restic.sh",
    "infra/scripts/zabbix-nightly-backup.sh",
    "infra/scripts/zabbix-isolated-restore-test.sh",
    "infra/scripts/verify-zabbix-restic-restore.sh",
}
DEPLOYED_TREE_ROOTS = (
    "app/backend/app",
    "app/backend/sql",
)


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def redact_secrets(value: Any) -> Any:
    """Replace values under secret-like keys with presence booleans."""
    if isinstance(value, dict):
        return {
            str(key): bool(item) if SENSITIVE_KEY.search(str(key)) else redact_secrets(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


def compose_files(root: Path) -> list[Path]:
    ignored_directories = {
        ".git",
        ".next",
        ".nuxt",
        ".pytest_cache",
        ".superpowers",
        ".turbo",
        ".venv",
        ".yarn",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "target",
        "venv",
        "vendor",
    }
    compose_names = {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}
    candidates: list[Path] = []
    for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in ignored_directories and not directory.endswith(".egg-info")
        )
        current_path = Path(current)
        candidates.extend(current_path / filename for filename in compose_names.intersection(filenames))
    return sorted(candidates, key=lambda path: path.relative_to(root).as_posix())


def parse_images(root: Path, paths: list[Path]) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    service_pattern = re.compile(r"^  ([A-Za-z0-9_.-]+):\s*$")
    image_pattern = re.compile(r"^\s{4}image:\s*(.*?)\s*$")
    build_pattern = re.compile(r"^\s{4}build:\s*(.*?)\s*$")

    for compose_path in paths:
        in_services = False
        service: str | None = None
        reference: str | None = None
        uses_build = False

        def flush() -> None:
            if service is None:
                return
            digest_match = re.search(r"@sha256:([0-9a-fA-F]{64})$", reference or "")
            digest = f"sha256:{digest_match.group(1).lower()}" if digest_match else None
            images.append(
                {
                    "service": service,
                    "compose_file": compose_path.relative_to(root).as_posix(),
                    "reference": reference,
                    "digest": digest,
                    "source": "build" if uses_build else "registry",
                    "immutable": digest is not None,
                }
            )

        for line in compose_path.read_text(encoding="utf-8").splitlines():
            if line == "services:":
                in_services = True
                continue
            if not in_services:
                continue
            stripped = line.strip()
            if stripped and not line.startswith((" ", "\t")) and not stripped.startswith("#"):
                flush()
                in_services = False
                service = None
                reference = None
                uses_build = False
                continue

            match_service = service_pattern.match(line)
            if match_service:
                flush()
                service = match_service.group(1)
                reference = None
                uses_build = False
                continue

            if service is None:
                continue
            match_image = image_pattern.match(line)
            if match_image:
                reference = match_image.group(1).strip().strip("'\"") or None
                continue
            match_build = build_pattern.match(line)
            if match_build:
                uses_build = True

        flush()

    return sorted(images, key=lambda row: (row["compose_file"], row["service"]))


def deployed_paths(root: Path, compose: list[Path]) -> list[Path]:
    selected = {path for path in compose if path.name.startswith("docker-compose")}
    for relative in DEPLOYED_NAMES:
        path = root / relative
        if path.is_file():
            selected.add(path)

    for relative in DEPLOYED_TREE_ROOTS:
        tree = root / relative
        if tree.is_dir():
            selected.update(
                path
                for path in tree.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix != ".pyc"
                and not path.name.startswith(".env")
            )

    for units_root in (root / "infra/systemd", root / "infra/psono/systemd"):
        if units_root.is_dir():
            selected.update(
                path
                for path in units_root.rglob("*")
                if path.is_file() and path.suffix in {".service", ".timer", ".socket", ".path"}
            )
    return sorted(selected, key=lambda path: path.relative_to(root).as_posix())


def file_hashes(root: Path, paths: list[Path]) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def read_versions(root: Path) -> dict[str, str]:
    inventory = root / "infra/ansible/inventory/group_vars/all.yml"
    if not inventory.is_file():
        return {}
    versions: dict[str, str] = {}
    for line in inventory.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([a-zA-Z0-9_]*version):\s*['\"]?([^'\"#\s]+)", line)
        if match and match.group(1) in VERSION_KEYS:
            versions[match.group(1)] = match.group(2)
    return dict(sorted(versions.items()))


def local_secret_presence(root: Path) -> dict[str, bool]:
    candidates = {
        "app/.env": root / "app/.env",
        "infra/psono/.env": root / "infra/psono/.env",
    }
    return {name: path.is_file() for name, path in sorted(candidates.items())}


def compare_production(
    local_images: list[dict[str, Any]],
    local_files: dict[str, str],
    local_versions: dict[str, str],
    facts: dict[str, Any],
) -> dict[str, Any]:
    production_images = facts.get("images", [])
    production_files = facts.get("deployed_files", {})
    production_versions = facts.get("versions", {})
    production_units = facts.get("systemd_units", [])

    image_by_service = {
        (str(row.get("compose_file", "")), str(row.get("service"))): row
        for row in production_images
    }
    image_divergences = []
    matched_images: set[tuple[str, str]] = set()
    blockers = []
    for image in local_images:
        service = image["service"]
        key = (str(image.get("compose_file", "")), service)
        observed = image_by_service.get(key)
        if observed is None and not key[0]:
            observed = next(
                (row for row in production_images if str(row.get("service")) == service),
                None,
            )
        if not image["digest"]:
            blockers.append(
                {"code": "image_digest_missing", "service": f"{key[0]}:{service}"}
            )
        if observed is None:
            image_divergences.append(f"{key[0] + ':' if key[0] else ''}{service}")
        elif not image["digest"] or observed.get("digest") != image["digest"]:
            image_divergences.append(f"{key[0] + ':' if key[0] else ''}{service}")
            matched_images.add(key)
        else:
            matched_images.add(key)

    for key in set(image_by_service) - matched_images:
        image_divergences.append(f"{key[0] + ':' if key[0] else ''}{key[1]}")

    file_divergences = sorted(
        path
        for path, digest in local_files.items()
        if path in production_files and production_files[path] != digest
    )
    unobserved_files = sorted(set(local_files) - set(production_files))

    version_divergences = []
    for name, expected in local_versions.items():
        observed = production_versions.get(name)
        if observed is None:
            continue
        if observed != expected and not str(observed).startswith(f"{expected}."):
            version_divergences.append(name)

    expected_units = {
        Path(path).name for path in local_files if "/systemd/" in path and Path(path).suffix in {".service", ".timer", ".socket", ".path"}
    }
    unit_divergences = sorted(set(production_units) ^ expected_units)

    divergences = {
        "images": sorted(set(image_divergences)),
        "files": file_divergences,
        "versions": sorted(version_divergences),
        "systemd_units": unit_divergences,
    }
    if divergences["images"]:
        blockers.append({"code": "production_image_divergence"})
    if divergences["files"]:
        blockers.append({"code": "production_file_divergence"})
    if divergences["versions"]:
        blockers.append({"code": "production_version_divergence"})
    if divergences["systemd_units"]:
        blockers.append({"code": "production_unit_divergence"})
    if unobserved_files:
        blockers.append({"code": "production_file_facts_missing", "count": len(unobserved_files)})

    return {
        "facts": redact_secrets(facts),
        "divergences": divergences,
        "unobserved": {"files": unobserved_files},
        "blockers": blockers,
    }


def build_manifest(root: Path, production_facts: dict[str, Any] | None) -> dict[str, Any]:
    commit = run_git(root, "rev-parse", "HEAD")
    dirty = bool(run_git(root, "status", "--porcelain"))
    compose = compose_files(root)
    images = parse_images(root, compose)
    deployed_file_hashes = file_hashes(root, deployed_paths(root, compose))
    versions = read_versions(root)
    units = sorted(
        path.name
        for units_root in (root / "infra/systemd", root / "infra/psono/systemd")
        if units_root.is_dir()
        for path in units_root.rglob("*")
        if path.is_file() and path.suffix in {".service", ".timer", ".socket", ".path"}
    )
    blockers = [
        {
            "code": "image_digest_missing",
            "service": f"{image['compose_file']}:{image['service']}",
        }
        for image in images
        if image["digest"] is None
    ]

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "target": "production" if production_facts is not None else "local",
        "git_commit": commit,
        "git_dirty": dirty,
        "images": images,
        "deployed_file_hashes": deployed_file_hashes,
        "versions": versions,
        "systemd_units": units,
        "secret_presence": local_secret_presence(root),
        "release_ready": not dirty and not blockers,
        "blockers": blockers,
    }

    if production_facts is not None:
        comparison = compare_production(images, deployed_file_hashes, versions, production_facts)
        manifest["production"] = comparison["facts"]
        manifest["divergences"] = comparison["divergences"]
        manifest["unobserved"] = comparison["unobserved"]
        manifest["blockers"].extend(comparison["blockers"])
        manifest["release_ready"] = (
            manifest["release_ready"]
            and not comparison["blockers"]
            and not comparison["unobserved"]["files"]
        )

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--production-facts", type=Path)
    args = parser.parse_args()

    try:
        facts = None
        if args.production_facts:
            facts = json.loads(args.production_facts.read_text(encoding="utf-8"))
            if not isinstance(facts, dict):
                raise ValueError("production facts must be a JSON object")
        manifest = build_manifest(args.repo_root.resolve(), facts)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(f".{args.output.name}.tmp")
        temporary.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)
    except (OSError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as error:
        print(f"release manifest failed: {error}", file=sys.stderr)
        return 2

    print(json.dumps({"output": str(args.output), "release_ready": manifest["release_ready"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
