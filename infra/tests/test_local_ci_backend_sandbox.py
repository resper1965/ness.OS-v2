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
        "pathlib.Path(os.environ['DOCKER_CALLS']).write_text(json.dumps(sys.argv[1:]))\n"
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
    args = json.loads(Path(env["DOCKER_CALLS"]).read_text())
    assert args[:2] == ["run", "--rm"]
    assert args[args.index("--network") + 1] == "none"
    assert "--read-only" in args
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert args[args.index("--security-opt") + 1] == "no-new-privileges"
    assert args[args.index("--user") + 1] == "65534:65534"
    assert f"type=bind,src={repo},dst=/src,readonly" in args
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
