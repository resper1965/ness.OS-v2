"""The trusted CI launcher must not give PR tests host privileges."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/local-ci-backend-sandbox.py"
IMAGE = "sha256:" + "a" * 64


@pytest.fixture
def checkout(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "tracked").write_text("test\n")
    (repo / "app/frontend").mkdir(parents=True)
    (repo / "app/frontend/package.json").write_text('{"name":"frontend-test"}\n')
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "entry = {'args': sys.argv[1:], 'stdin_bytes': len(sys.stdin.buffer.read()) if '-i' in sys.argv else 0}\n"
        "with open(os.environ['DOCKER_CALLS'], 'a') as out: out.write(json.dumps(entry) + '\\n')\n"
        "if os.environ.get('FAKE_DOCKER_SCAN_ERROR') and ('sha256:' + 'd' * 64) in sys.argv: sys.stderr.write('scan failed\\n')\n"
    )
    docker.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "DOCKER_CALLS": str(tmp_path / "calls.json"),
    }
    return repo, commit, env


def test_backend_tests_run_without_network_socket_or_secret_mount(checkout):
    repo, commit, env = checkout
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--image",
            IMAGE,
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    args = json.loads(Path(env["DOCKER_CALLS"]).read_text().splitlines()[0])["args"]
    assert args[:2] == ["run", "--rm"]
    assert args[args.index("--network") + 1] == "none"
    assert "--read-only" in args
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert args[args.index("--security-opt") + 1] == "no-new-privileges"
    assert args[args.index("--user") + 1] == "65534:65534"
    assert f"type=bind,src={repo / 'app/backend'},dst=/src/app/backend,readonly" in args
    assert f"type=bind,src={repo / 'cli'},dst=/src/cli,readonly" in args
    assert f"type=bind,src={repo},dst=/src,readonly" not in args
    assert not any("docker.sock" in value or "/etc/ness-os" in value for value in args)
    assert args[-6:] == [
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "app/backend/tests",
    ]


def test_wrong_commit_stops_before_docker(checkout):
    repo, _, env = checkout
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--commit",
            "0" * 40,
            "--image",
            IMAGE,
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not Path(env["DOCKER_CALLS"]).exists()


def test_symlinked_source_directory_stops_before_docker(checkout):
    repo, _, env = checkout
    outside = repo.parent / "outside"
    outside.mkdir()
    (outside / "private.txt").write_text("private fixture\n")
    (repo / "cli").symlink_to(outside, target_is_directory=True)
    subprocess.run(["git", "-C", str(repo), "add", "cli"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "symlink fixture"], check=True
    )
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--image",
            IMAGE,
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not Path(env["DOCKER_CALLS"]).exists()


def test_frontend_archive_runs_lint_and_build_without_host_mount(checkout):
    repo, commit, env = checkout
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--image",
            IMAGE,
            "--frontend-image",
            "sha256:" + "b" * 64,
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls = [
        json.loads(line) for line in Path(env["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert len(calls) == 2
    frontend = calls[1]["args"]
    assert calls[1]["stdin_bytes"] > 0
    assert frontend[:2] == ["run", "--rm"]
    assert frontend[frontend.index("--network") + 1] == "none"
    assert frontend[frontend.index("--user") + 1] == "65534:65534"
    assert "--read-only" in frontend
    assert "--mount" not in frontend
    assert frontend[frontend.index("--entrypoint") + 1] == "sh"
    assert frontend[-2] == "-c"
    assert "npm run lint" in frontend[-1]
    assert "npm run build -- --configLoader runner" in frontend[-1]
    assert not any(
        "docker.sock" in value or "/etc/ness-os" in value for value in frontend
    )


def test_python_quality_checks_run_in_separate_unprivileged_image(checkout):
    repo, commit, env = checkout
    lint_image = "sha256:" + "c" * 64
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--image",
            IMAGE,
            "--lint-image",
            lint_image,
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls = [
        json.loads(line) for line in Path(env["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert len(calls) == 2
    lint = calls[1]["args"]
    assert lint[lint.index("--network") + 1] == "none"
    assert "--read-only" in lint
    assert lint[lint.index("--user") + 1] == "65534:65534"
    assert lint[lint.index("--cap-drop") + 1] == "ALL"
    assert "RUFF_CACHE_DIR=/tmp/ruff" in lint
    assert f"type=bind,src={repo / 'app/backend'},dst=/src/app/backend,readonly" in lint
    assert f"type=bind,src={repo / 'cli'},dst=/src/cli,readonly" in lint
    assert f"type=bind,src={repo},dst=/src,readonly" not in lint
    assert lint_image in lint
    assert "black --check app/backend" in lint[-1]
    assert "flake8 app/backend" in lint[-1]
    assert "ruff check app/backend/app" in lint[-1]
    assert "ruff format --check app/backend/app" in lint[-1]
    assert "mypy app/backend/app --ignore-missing-imports" in lint[-1]
    assert not any("docker.sock" in value or "/etc/ness-os" in value for value in lint)


def test_secret_scan_rejects_scanner_error_even_when_exit_code_is_zero(checkout):
    repo, commit, env = checkout
    env["FAKE_DOCKER_SCAN_ERROR"] = "1"
    approved_ignore = repo.parent / "approved-ignore"
    approved_ignore.write_text("")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--image",
            IMAGE,
            "--scan-image",
            "sha256:" + "d" * 64,
            "--scan-ignore",
            str(approved_ignore),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "scan failed" not in result.stdout
    assert "exit=0" in result.stderr
    calls = [
        json.loads(line) for line in Path(env["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert len(calls) == 2


def test_secret_scan_is_read_only_and_fixes_git_safe_directory(checkout):
    repo, commit, env = checkout
    approved_ignore = repo.parent / "approved-ignore"
    approved_ignore.write_text("")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--image",
            IMAGE,
            "--scan-image",
            "sha256:" + "d" * 64,
            "--scan-ignore",
            str(approved_ignore),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "secret_scan_sandbox=PASS" in result.stdout
    calls = [
        json.loads(line) for line in Path(env["DOCKER_CALLS"]).read_text().splitlines()
    ]
    assert len(calls) == 2
    scan = calls[1]["args"]
    assert scan[scan.index("--network") + 1] == "none"
    assert "--read-only" in scan
    assert scan[scan.index("--user") + 1] == "65534:65534"
    assert "GIT_CONFIG_KEY_0=safe.directory" in scan
    assert "GIT_CONFIG_VALUE_0=/src" in scan
    assert "GITLEAKS_CONFIG_TOML=[extend]\nuseDefault=true\n" in scan
    assert f"type=bind,src={repo},dst=/src,readonly" in scan
    assert f"type=bind,src={approved_ignore},dst=/trusted-ignore,readonly" in scan
    assert "--gitleaks-ignore-path" in scan
    assert scan[scan.index("--gitleaks-ignore-path") + 1] == "/trusted-ignore"
    assert "--ignore-gitleaks-allow" in scan
    assert scan[-1] == "."
    assert not any("docker.sock" in value or "/etc/ness-os" in value for value in scan)
