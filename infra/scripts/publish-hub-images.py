#!/usr/bin/env python3
"""Build and publish immutable Hub images from a verified local checkout."""

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
REGISTRY = re.compile(r"[a-z0-9][a-z0-9./:_-]*\Z")


def command(*args: str) -> str:
    result = subprocess.run(args, cwd=ROOT, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True, help="Exact reviewed Git commit")
    parser.add_argument("--registry", required=True, help="Private registry namespace, without image name")
    parser.add_argument("--output", type=Path, required=True, help="New release reference JSON")
    args = parser.parse_args()
    registry = args.registry.rstrip("/")
    if not COMMIT.fullmatch(args.commit) or not REGISTRY.fullmatch(registry) or "//" in registry:
        parser.error("invalid commit or registry namespace")
    if args.output.exists():
        parser.error("release reference already exists")
    if command("git", "rev-parse", "HEAD") != args.commit:
        parser.error("checkout does not match reviewed commit")
    if command("git", "status", "--porcelain", "--untracked-files=all"):
        parser.error("checkout is not clean")

    subprocess.run(["bash", "infra/scripts/hub-release-checks.sh"], cwd=ROOT, check=True)
    if command("git", "rev-parse", "HEAD") != args.commit or command(
        "git", "status", "--porcelain", "--untracked-files=all"
    ):
        parser.error("checkout changed during release checks")

    images = {}
    with tempfile.TemporaryDirectory(prefix="ness-release-") as scratch:
        for name, dockerfile, context in (
            ("api", "app/Dockerfile", "app"),
            ("frontend", "app/frontend/Dockerfile", "app/frontend"),
        ):
            image = f"{registry}/ninf-{name}"
            metadata = Path(scratch) / f"{name}.json"
            subprocess.run(
                [
                    "docker", "buildx", "build", "--pull", "--push",
                    "--metadata-file", str(metadata), "--file", dockerfile,
                    "--tag", f"{image}:{args.commit}", context,
                ],
                cwd=ROOT,
                check=True,
            )
            digest = json.loads(metadata.read_text(encoding="utf-8")).get("containerimage.digest")
            if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
                raise RuntimeError(f"{name} build did not return a valid image digest")
            images[name] = f"{image}@{digest}"

    result = {"commit": args.commit, **images}
    with args.output.open("x", encoding="utf-8") as release_file:
        release_file.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
