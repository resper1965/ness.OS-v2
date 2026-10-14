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
    parser.add_argument("--frontend-image", help="Immutable local frontend image ID")
    parser.add_argument(
        "--lint-image", help="Immutable local Python quality-tools image ID"
    )
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    if (
        not SHA.fullmatch(args.commit)
        or not IMAGE.fullmatch(args.image)
        or (args.frontend_image and not IMAGE.fullmatch(args.frontend_image))
        or (args.lint_image and not IMAGE.fullmatch(args.lint_image))
    ):
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

    if args.lint_image:
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
                "MYPY_CACHE_DIR=/tmp/mypy",
                "--mount",
                f"type=bind,src={repo},dst=/src,readonly",
                "--workdir",
                "/src",
                "--entrypoint",
                "sh",
                args.lint_image,
                "-c",
                "set -eu; black --check app/backend; "
                "flake8 app/backend --count --select=E9,F63,F7,F82 --show-source --statistics; "
                "ruff check app/backend/app; ruff format --check app/backend/app; "
                "mypy app/backend/app --ignore-missing-imports",
            ],
            cwd=repo,
            check=True,
        )
        print("python_quality_sandbox=PASS")

    if args.frontend_image:
        archive = subprocess.check_output(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "archive",
                args.commit,
                "app/frontend",
            ]
        )
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-i",
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=64m",
                "--tmpfs",
                "/work:rw,nosuid,nodev,mode=1777,size=512m",
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
                "--workdir",
                "/work",
                "--entrypoint",
                "sh",
                args.frontend_image,
                "-c",
                "tar -xf - -C /work && ln -s /app/node_modules /work/app/frontend/node_modules && cd /work/app/frontend && npm run lint && npm run build -- --configLoader runner",
            ],
            input=archive,
            cwd=repo,
            check=True,
        )
        print("frontend_sandbox=PASS")


if __name__ == "__main__":
    main()
