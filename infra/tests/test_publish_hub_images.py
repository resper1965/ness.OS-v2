"""Publishing must be tied to a clean commit and immutable digests."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts/publish-hub-images.py"


def fixture(tmp_path):
    root = tmp_path / "repo"
    (root / "infra/scripts").mkdir(parents=True)
    (root / "app/frontend").mkdir(parents=True)
    (root / "app/Dockerfile").write_text("FROM scratch\n")
    (root / "app/frontend/Dockerfile").write_text("FROM scratch\n")
    shutil.copy2(SCRIPT, root / "infra/scripts/publish-hub-images.py")
    checks = root / "infra/scripts/hub-release-checks.sh"
    checks.write_text(
        "#!/bin/sh\nprintf checked > \"$CHECK_MARKER\"\n"
        "if [ -n \"${CHECK_MUTATE:-}\" ]; then printf changed > changed-after-checks; fi\n"
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['DOCKER_CALLS'], 'a') as f: f.write(' '.join(args) + '\\n')\n"
        "if args[:2] == ['buildx', 'build']:\n"
        "    digest = 'bad' if os.getenv('BAD_DIGEST') else 'sha256:' + ('a' if 'ninf-api:' in ' '.join(args) else 'b') * 64\n"
        "    pathlib.Path(args[args.index('--metadata-file') + 1]).write_text(json.dumps({'containerimage.digest': digest}))\n"
        "if args[:1] == ['pull'] and os.getenv('PULL_FAIL'): sys.exit(1)\n"
    )
    docker.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "DOCKER_CALLS": str(tmp_path / "docker-calls"),
        "CHECK_MARKER": str(tmp_path / "checks-ran"),
    }
    output = tmp_path / "release.json"
    command = [sys.executable, str(root / "infra/scripts/publish-hub-images.py"), "--commit", commit, "--registry", "registry.example/ness", "--output", str(output)]
    return root, env, output, command, commit


def test_clean_commit_runs_checks_and_records_two_immutable_images(tmp_path):
    root, env, output, command, commit = fixture(tmp_path)
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert Path(env["CHECK_MARKER"]).read_text() == "checked"
    assert json.loads(output.read_text()) == {
        "commit": commit,
        "api": "registry.example/ness/ninf-api@sha256:" + "a" * 64,
        "frontend": "registry.example/ness/ninf-frontend@sha256:" + "b" * 64,
    }
    calls = Path(env["DOCKER_CALLS"]).read_text().splitlines()
    assert len(calls) == 4
    assert all("--push" in call and "--metadata-file" in call for call in calls[:2])
    assert calls[2:] == [
        "pull registry.example/ness/ninf-api@sha256:" + "a" * 64,
        "pull registry.example/ness/ninf-frontend@sha256:" + "b" * 64,
    ]


def test_pull_failure_never_creates_release_reference(tmp_path):
    root, env, output, command, _ = fixture(tmp_path)
    result = subprocess.run(
        command, cwd=root, env={**env, "PULL_FAIL": "1"}, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert not output.exists()


def test_dirty_tree_stops_before_checks_or_push(tmp_path):
    root, env, output, command, _ = fixture(tmp_path)
    (root / "dirty").write_text("change")
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert not output.exists()
    assert not Path(env["CHECK_MARKER"]).exists()
    assert not Path(env["DOCKER_CALLS"]).exists()


def test_invalid_digest_never_creates_release_reference(tmp_path):
    root, env, output, command, _ = fixture(tmp_path)
    result = subprocess.run(command, cwd=root, env={**env, "BAD_DIGEST": "1"}, capture_output=True, text=True)
    assert result.returncode != 0
    assert not output.exists()


def test_checks_cannot_change_source_before_build(tmp_path):
    root, env, output, command, _ = fixture(tmp_path)
    result = subprocess.run(
        command, cwd=root, env={**env, "CHECK_MUTATE": "1"}, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert not output.exists()
    assert not Path(env["DOCKER_CALLS"]).exists()
