#!/usr/bin/env python3
"""Compare two stopped GLPI state trees without printing paths or contents."""

import argparse
import hashlib
import json
import os
import pathlib
import stat
import sys


def _snapshot(root: pathlib.Path) -> dict:
    digest = hashlib.sha256()
    files = size = 0

    def visit(path: pathlib.Path, relative: str) -> None:
        nonlocal files, size
        info = path.lstat()
        record = [relative, stat.S_IFMT(info.st_mode), stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid]
        if stat.S_ISREG(info.st_mode):
            content = hashlib.sha256()
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    content.update(chunk)
            record.extend([info.st_size, content.hexdigest(), info.st_nlink])
            files += 1
            size += info.st_size
        elif stat.S_ISLNK(info.st_mode):
            record.append(os.readlink(path))
        elif not stat.S_ISDIR(info.st_mode):
            raise ValueError("unsupported file type in GLPI state tree")
        record.append([(key, os.getxattr(path, key, follow_symlinks=False).hex())
                       for key in sorted(os.listxattr(path, follow_symlinks=False))])
        digest.update(json.dumps(record, separators=(",", ":")).encode() + b"\n")
        if stat.S_ISDIR(info.st_mode):
            for entry in sorted(os.scandir(path), key=lambda item: item.name):
                visit(path / entry.name, f"{relative}/{entry.name}")

    visit(root, ".")
    return {"digest": digest.digest(), "files": files, "bytes": size}


def compare_trees(before: pathlib.Path, after: pathlib.Path) -> dict:
    before = pathlib.Path(before)
    after = pathlib.Path(after)
    if before.is_symlink() or after.is_symlink() or not before.is_dir() or not after.is_dir():
        raise ValueError("both GLPI state roots must be real directories")
    if os.path.samefile(before, after):
        raise ValueError("GLPI state roots must be distinct")
    old = _snapshot(before)
    new = _snapshot(after)
    if old != new:
        raise ValueError("GLPI state trees differ")
    return {"files": old["files"], "bytes": old["bytes"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=pathlib.Path)
    parser.add_argument("after", type=pathlib.Path)
    args = parser.parse_args()
    try:
        result = compare_trees(args.before, args.after)
    except (OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print(f"GLPI state compare BLOCKED: {reason}", file=sys.stderr)
        return 1
    print(f"GLPI state compare PASS: files={result['files']} bytes={result['bytes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
