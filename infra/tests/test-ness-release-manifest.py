import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "infra/scripts/ness-release-manifest.py"


def write_fixture_repo(root: Path, compose: str) -> Path:
    (root / "app").mkdir(parents=True)
    (root / "infra/systemd").mkdir(parents=True)
    (root / "infra/ansible/inventory/group_vars").mkdir(parents=True)
    (root / "app/docker-compose.yml").write_text(compose, encoding="utf-8")
    (root / "app/Caddyfile").write_text(":80 { respond ok }\n", encoding="utf-8")
    (root / "infra/systemd/ness-test.timer").write_text(
        "[Timer]\nOnCalendar=daily\n", encoding="utf-8"
    )
    (root / "infra/ansible/inventory/group_vars/all.yml").write_text(
        'zabbix_version: "7.0"\nmariadb_version: "10.11"\n',
        encoding="utf-8",
    )
    return root


def initialize_git(root: Path) -> str:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "release-test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Release Test"], check=True
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "fixture baseline"], check=True
    )
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()


def generate(
    root: Path,
    output: Path,
    facts: dict | None = None,
    extra_args: list[str] | None = None,
) -> dict:
    command = [
        sys.executable,
        str(GENERATOR),
        "--repo-root",
        str(root),
        "--output",
        str(output),
    ]
    if facts is not None:
        facts_file = output.with_suffix(".production-facts.json")
        facts_file.write_text(json.dumps(facts), encoding="utf-8")
        command.extend(["--production-facts", str(facts_file)])
    if extra_args:
        command.extend(extra_args)
    subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(output.read_text(encoding="utf-8"))


def test_git_state_reports_clean_then_dirty_repository(tmp_path: Path) -> None:
    compose = "services:\n  db:\n    image: postgres:17@sha256:" + "a" * 64 + "\n"
    root = write_fixture_repo(tmp_path / "repo", compose)
    expected_commit = initialize_git(root)

    clean = generate(root, tmp_path / "clean.json")
    assert clean["git_commit"] == expected_commit
    assert clean["git_dirty"] is False

    (root / "app/Caddyfile").write_text(":80 { respond changed }\n", encoding="utf-8")
    dirty = generate(root, tmp_path / "dirty.json")
    assert dirty["git_commit"] == expected_commit
    assert dirty["git_dirty"] is True


def test_hashes_cover_source_mounted_into_production_containers(tmp_path: Path) -> None:
    root = write_fixture_repo(
        tmp_path / "repo",
        "services:\n  db:\n    image: postgres:17@sha256:" + "a" * 64 + "\n",
    )
    source = root / "app/backend/app/main.py"
    source.parent.mkdir(parents=True)
    source.write_text("app_version = 'fixture'\n", encoding="utf-8")
    frontend_source = root / "app/frontend/src/main.tsx"
    frontend_source.parent.mkdir(parents=True)
    frontend_source.write_text("export {}\n", encoding="utf-8")
    dockerfile = root / "app/backend/Dockerfile"
    dockerfile.parent.mkdir(parents=True, exist_ok=True)
    dockerfile.write_text("FROM python:3.13\n", encoding="utf-8")
    initialize_git(root)

    manifest = generate(root, tmp_path / "manifest.json")

    expected_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    assert manifest["deployed_file_hashes"]["app/backend/app/main.py"] == expected_hash
    assert "app/frontend/src/main.tsx" not in manifest["deployed_file_hashes"]
    assert "app/backend/Dockerfile" not in manifest["deployed_file_hashes"]


def test_hashes_cover_standalone_database_migrations(tmp_path: Path) -> None:
    root = write_fixture_repo(
        tmp_path / "repo",
        "services:\n  db:\n    image: postgres:17@sha256:" + "a" * 64 + "\n",
    )
    migration = root / "infra/sql/20260908_asset_type_unknown.sql"
    migration.parent.mkdir(parents=True)
    migration.write_text("ALTER TYPE asset_type ADD VALUE 'unknown';\n", encoding="utf-8")
    initialize_git(root)

    manifest = generate(root, tmp_path / "manifest.json")

    expected_hash = hashlib.sha256(migration.read_bytes()).hexdigest()
    assert manifest["deployed_file_hashes"]["infra/sql/20260908_asset_type_unknown.sql"] == expected_hash


def test_hashes_cover_installed_service_entrypoints_and_host_configuration(
    tmp_path: Path,
) -> None:
    root = write_fixture_repo(
        tmp_path / "repo",
        "services:\n  db:\n    image: postgres:17@sha256:" + "a" * 64 + "\n",
    )
    paths = (
        "infra/scripts/aiops-isolated-restore-test.sh",
        "infra/scripts/hub-clean-engine-restore.sh",
        "infra/scripts/hub-cmdb-sync.sh",
        "infra/scripts/hub-health-history.py",
        "infra/scripts/hub-integration-monitor.sh",
        "infra/psono/scripts/backup.sh",
        "infra/psono/scripts/restore-verify.sh",
        "infra/netplan/60-ness-zabbix-route.yaml",
    )
    for relative in paths:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    initialize_git(root)

    manifest = generate(root, tmp_path / "manifest.json")

    assert set(paths) <= set(manifest["deployed_file_hashes"])


def test_compose_discovery_skips_dependency_and_build_directories(tmp_path: Path) -> None:
    root = write_fixture_repo(
        tmp_path / "repo",
        "services:\n  db:\n    image: postgres:17@sha256:" + "a" * 64 + "\n",
    )
    ignored_compose_files = [
        root / "app/node_modules/package/docker-compose.yml",
        root / "app/.next/cache/docker-compose.yml",
        root / "app/.venv/share/docker-compose.yml",
    ]
    for compose in ignored_compose_files:
        compose.parent.mkdir(parents=True, exist_ok=True)
        compose.write_text(
            "services:\n  decoy:\n    image: ignored:latest\n", encoding="utf-8"
        )
    initialize_git(root)

    manifest = generate(root, tmp_path / "manifest.json")

    assert [(row["compose_file"], row["service"]) for row in manifest["images"]] == [
        ("app/docker-compose.yml", "db")
    ]


def test_compose_discovery_skips_git_worktree_checkouts(tmp_path: Path) -> None:
    root = write_fixture_repo(
        tmp_path / "repo",
        "services:\n  db:\n    image: postgres:17@sha256:" + "a" * 64 + "\n",
    )
    auxiliary = root / ".worktrees" / "candidate" / "docker-compose.yml"
    auxiliary.parent.mkdir(parents=True)
    auxiliary.write_text(
        "services:\n  accidental:\n    image: registry.example/accidental:latest\n",
        encoding="utf-8",
    )
    initialize_git(root)

    manifest = generate(root, tmp_path / "manifest.json")

    assert [(row["compose_file"], row["service"]) for row in manifest["images"]] == [
        ("app/docker-compose.yml", "db")
    ]


def test_explicit_compose_scope_ignores_unselected_files(tmp_path: Path) -> None:
    root = write_fixture_repo(
        tmp_path / "repo",
        "services:\n  db:\n    image: postgres:17@sha256:" + "a" * 64 + "\n",
    )
    extra = root / "extra-compose.yml"
    extra.write_text(
        "services:\n  excluded:\n    image: registry.example/excluded:latest\n",
        encoding="utf-8",
    )
    initialize_git(root)

    manifest = generate(
        root,
        tmp_path / "manifest.json",
        extra_args=["--compose-file", "app/docker-compose.yml"],
    )

    assert [(row["compose_file"], row["service"]) for row in manifest["images"]] == [
        ("app/docker-compose.yml", "db")
    ]


def test_manifest_accepts_immutable_service_image_override(tmp_path: Path) -> None:
    root = write_fixture_repo(
        tmp_path / "repo",
        "services:\n  api:\n    build: .\n",
    )
    initialize_git(root)
    reference = "registry.example/ness/api@sha256:" + "b" * 64

    manifest = generate(
        root,
        tmp_path / "manifest.json",
        extra_args=[
            "--compose-file",
            "app/docker-compose.yml",
            "--image-ref",
            f"api={reference}",
        ],
    )

    assert manifest["images"] == [
        {
            "compose_file": "app/docker-compose.yml",
            "digest": "sha256:" + "b" * 64,
            "immutable": True,
            "reference": reference,
            "service": "api",
            "source": "build",
        }
    ]


def test_manifest_rejects_mutable_service_image_override(tmp_path: Path) -> None:
    root = write_fixture_repo(tmp_path / "repo", "services:\n  api:\n    build: .\n")
    initialize_git(root)

    command = [
        sys.executable,
        str(GENERATOR),
        "--repo-root",
        str(root),
        "--output",
        str(tmp_path / "manifest.json"),
        "--image-ref",
        "api=registry.example/ness/api:latest",
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    assert result.returncode == 2
    assert "immutable image reference" in result.stderr


def test_manifest_rejects_unknown_override_service(tmp_path: Path) -> None:
    root = write_fixture_repo(tmp_path / "repo", "services:\n  api:\n    build: .\n")
    initialize_git(root)

    command = [
        sys.executable,
        str(GENERATOR),
        "--repo-root",
        str(root),
        "--output",
        str(tmp_path / "manifest.json"),
        "--image-ref",
        "absent=registry.example/ness/api@sha256:" + "c" * 64,
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    assert result.returncode == 2
    assert "unknown image-ref service" in result.stderr


def test_manifest_rejects_different_api_worker_image_override(tmp_path: Path) -> None:
    root = write_fixture_repo(
        tmp_path / "repo",
        "services:\n  api:\n    build: .\n  worker-alerts:\n    build: .\n",
    )
    initialize_git(root)

    command = [
        sys.executable,
        str(GENERATOR),
        "--repo-root",
        str(root),
        "--output",
        str(tmp_path / "manifest.json"),
        "--image-ref",
        "api=registry.example/ness/api@sha256:" + "d" * 64,
        "--image-ref",
        "worker-alerts=registry.example/ness/api@sha256:" + "e" * 64,
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    assert result.returncode == 2
    assert "API worker image references must match" in result.stderr


def test_unpinned_image_is_reported_as_a_release_blocker(tmp_path: Path) -> None:
    root = write_fixture_repo(
        tmp_path / "repo",
        "services:\n  db:\n    image: postgres:17\nvolumes:\n  data:\nnetworks:\n  app:\n",
    )
    initialize_git(root)

    manifest = generate(root, tmp_path / "manifest.json")

    image = next(image for image in manifest["images"] if image["service"] == "db")
    assert [image["service"] for image in manifest["images"]] == ["db"]
    assert image["digest"] is None
    assert {blocker["code"] for blocker in manifest["blockers"]} >= {
        "image_digest_missing"
    }
    assert manifest["release_ready"] is False


def test_unpinned_image_has_one_blocker_with_production_facts(tmp_path: Path) -> None:
    root = write_fixture_repo(
        tmp_path / "repo",
        "services:\n  db:\n    image: postgres:17\n",
    )
    initialize_git(root)
    facts = {
        "images": [
            {
                "compose_file": "app/docker-compose.yml",
                "service": "db",
                "digest": "sha256:" + "a" * 64,
            }
        ],
        "deployed_files": {},
        "versions": {},
        "systemd_units": ["ness-test.timer"],
    }

    manifest = generate(root, tmp_path / "production.json", facts)

    assert manifest["blockers"].count(
        {"code": "image_digest_missing", "service": "app/docker-compose.yml:db"}
    ) == 1
    assert {blocker["code"] for blocker in manifest["blockers"]} >= {
        "production_image_divergence"
    }
    assert manifest["release_ready"] is False


def test_production_file_hash_difference_is_reported(tmp_path: Path) -> None:
    digest = "b" * 64
    compose = "services:\n  db:\n    image: postgres:17@sha256:" + digest + "\n"
    root = write_fixture_repo(tmp_path / "repo", compose)
    initialize_git(root)
    facts = {
        "host": "zabbix-srv01",
        "images": [],
        "deployed_files": {"app/docker-compose.yml": "0" * 64},
        "versions": {"zabbix_server": "7.0.27"},
        "systemd_units": ["ness-zabbix-backup.timer"],
    }

    manifest = generate(root, tmp_path / "production.json", facts)

    assert manifest["production"]["host"] == "zabbix-srv01"
    assert "app/docker-compose.yml" in manifest["divergences"]["files"]
    expected_hash = hashlib.sha256((root / "app/docker-compose.yml").read_bytes()).hexdigest()
    assert manifest["deployed_file_hashes"]["app/docker-compose.yml"] == expected_hash
    assert manifest["release_ready"] is False


def test_production_only_image_is_reported_as_divergence(tmp_path: Path) -> None:
    local_digest = "d" * 64
    root = write_fixture_repo(
        tmp_path / "repo",
        "services:\n  db:\n    image: postgres:17@sha256:" + local_digest + "\n",
    )
    initialize_git(root)
    facts = {
        "images": [
            {
                "compose_file": "app/docker-compose.yml",
                "service": "legacy",
                "digest": "sha256:" + "e" * 64,
            }
        ],
        "deployed_files": {},
        "versions": {},
        "systemd_units": [],
    }

    manifest = generate(root, tmp_path / "production.json", facts)

    assert manifest["divergences"]["images"] == ["app/docker-compose.yml:db", "app/docker-compose.yml:legacy"]


def test_sensitive_production_values_are_replaced_by_presence_booleans(
    tmp_path: Path,
) -> None:
    compose = "services:\n  db:\n    image: postgres:17@sha256:" + "c" * 64 + "\n"
    root = write_fixture_repo(tmp_path / "repo", compose)
    initialize_git(root)
    facts = {
        "host": "aiops-prod",
        "images": [],
        "deployed_files": {},
        "versions": {},
        "systemd_units": [],
        "environment": {"CONTABO_SECRET_KEY": "fixture-placeholder"},
    }

    manifest = generate(root, tmp_path / "production.json", facts)
    serialized = json.dumps(manifest)

    assert "fixture-placeholder" not in serialized
    assert manifest["production"]["environment"]["CONTABO_SECRET_KEY"] is True
