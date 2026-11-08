#!/usr/bin/env python3
"""Fail if a public skill tree contains source PDFs or generated evidence data."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


FORBIDDEN_SUFFIXES = {".pdf", ".jsonl"}
FORBIDDEN_NAMES = {"index_meta.json"}
FORBIDDEN_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "index-output",
    "rendered",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--max-file-mib", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"Repository directory not found: {root}")

    problems: list[str] = []
    limit = int(args.max_file_mib * 1024 * 1024)
    for current, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in FORBIDDEN_DIRS]
        current_path = Path(current)
        for name in files:
            path = current_path / name
            relative = path.relative_to(root)
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                problems.append(f"forbidden evidence file: {relative}")
            if name in FORBIDDEN_NAMES:
                problems.append(f"forbidden generated metadata: {relative}")
            if path.stat().st_size > limit:
                problems.append(
                    f"file exceeds {args.max_file_mib:g} MiB review limit: {relative}"
                )

    if problems:
        print("Public-release audit failed:")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)

    print("Public-release audit passed: no PDFs, JSONL indexes, index metadata, or oversized files found.")


if __name__ == "__main__":
    main()
