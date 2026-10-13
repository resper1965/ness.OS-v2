#!/usr/bin/env python3
"""Run backend tests from an exact clean commit without host privileges."""

import argparse
import re
import subprocess
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
IMAGE = re.compile(r"sha256:[0-9a-f]{64}\Z")


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            *args,
        ],
        text=True,
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--image", required=True, help="Immutable local image ID")
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    if not SHA.fullmatch(args.commit) or not IMAGE.fullmatch(args.image):
        parser.error("commit or image ID is not immutable")
    if git(repo, "rev-parse", "HEAD") != args.commit or git(
        repo, "status", "--porcelain", "--untracked-files=all"
    ):
        parser.error("checkout is not clean at the requested commit")

    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=256m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "256",
            "--memory",
            "2g",
            "--user",
            "65534:65534",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "PYTHONPATH=/src:/src/app/backend",
            "--mount",
            f"type=bind,src={repo},dst=/src,readonly",
            "--workdir",
            "/src",
            "--entrypoint",
            "python",
            args.image,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "app/backend/tests",
        ],
        cwd=repo,
        check=True,
    )
    print("backend_sandbox=PASS")


if __name__ == "__main__":
    main()
