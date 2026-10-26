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
    parser.add_argument("--scan-image", help="Immutable local Gitleaks image ID")
    parser.add_argument(
        "--scan-ignore", type=Path, help="Reviewed ignore file outside checkout"
    )
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    if (
        not SHA.fullmatch(args.commit)
        or not IMAGE.fullmatch(args.image)
        or (args.frontend_image and not IMAGE.fullmatch(args.frontend_image))
        or (args.lint_image and not IMAGE.fullmatch(args.lint_image))
        or (args.scan_image and not IMAGE.fullmatch(args.scan_image))
    ):
        parser.error("commit or image ID is not immutable")
    if git(repo, "rev-parse", "HEAD") != args.commit or git(
        repo, "status", "--porcelain", "--untracked-files=all"
    ):
        parser.error("checkout is not clean at the requested commit")
    for source in (repo / "app/backend", repo / "cli"):
        if source.resolve() != source:
            parser.error("source mount must not traverse a symlink")
    if args.scan_image and not args.scan_ignore:
        parser.error("secret scan requires an external reviewed ignore file")
    if args.scan_ignore and not args.scan_image:
        parser.error("ignore file requires a secret scan image")
    if args.scan_ignore:
        ignore = args.scan_ignore.resolve(strict=True)
        if not ignore.is_file() or ignore.is_relative_to(repo):
            parser.error("ignore file must be a regular file outside checkout")

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
            f"type=bind,src={repo / 'app/backend'},dst=/src/app/backend,readonly",
            "--mount",
            f"type=bind,src={repo / 'cli'},dst=/src/cli,readonly",
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
                "--env",
                "RUFF_CACHE_DIR=/tmp/ruff",
                "--mount",
                f"type=bind,src={repo / 'app/backend'},dst=/src/app/backend,readonly",
                "--mount",
                f"type=bind,src={repo / 'cli'},dst=/src/cli,readonly",
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

    if args.scan_image:
        scan = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=128m",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "128",
                "--memory",
                "1g",
                "--user",
                "65534:65534",
                "--env",
                "GIT_CONFIG_COUNT=1",
                "--env",
                "GIT_CONFIG_KEY_0=safe.directory",
                "--env",
                "GIT_CONFIG_VALUE_0=/src",
                "--env",
                "GITLEAKS_CONFIG_TOML=[extend]\nuseDefault=true\n",
                "--mount",
                f"type=bind,src={repo},dst=/src,readonly",
                "--mount",
                f"type=bind,src={ignore},dst=/trusted-ignore,readonly",
                "--workdir",
                "/src",
                args.scan_image,
                "git",
                "--redact",
                "--no-banner",
                "--log-level",
                "error",
                "--ignore-gitleaks-allow",
                "--gitleaks-ignore-path",
                "/trusted-ignore",
                ".",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        if scan.returncode != 0 or scan.stderr.strip():
            raise RuntimeError(
                f"secret scan failed or reported an error "
                f"(exit={scan.returncode}, stderr_bytes={len(scan.stderr)})"
            )
        print("secret_scan_sandbox=PASS")

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
