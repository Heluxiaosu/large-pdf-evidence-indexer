#!/usr/bin/env python3
"""Render selected 1-based PDF pages to PNG files for visual verification."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def parse_page_spec(value: str) -> list[int]:
    pages: set[int] = set()
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            left, right = token.split("-", 1)
            start, end = int(left), int(right)
            if start < 1 or end < start:
                raise argparse.ArgumentTypeError(f"Invalid range: {token}")
            pages.update(range(start, end + 1))
        else:
            page = int(token)
            if page < 1:
                raise argparse.ArgumentTypeError(f"Invalid page: {token}")
            pages.add(page)
    if not pages:
        raise argparse.ArgumentTypeError("No pages selected")
    return sorted(pages)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages", type=parse_page_spec, required=True, help="Pages such as 12,14,64-68")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path = args.pdf.expanduser().resolve()
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise SystemExit("pdftoppm is required; install Poppler first.")

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for page in args.pages:
        output_path = output_dir / f"page-{page:04d}.png"
        if output_path.exists() and not args.overwrite:
            print(output_path)
            continue
        prefix = output_path.with_suffix("")
        result = subprocess.run(
            [
                pdftoppm,
                "-f",
                str(page),
                "-l",
                str(page),
                "-r",
                str(args.dpi),
                "-png",
                "-singlefile",
                str(pdf_path),
                str(prefix),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or f"Failed to render page {page}")
        print(output_path)


if __name__ == "__main__":
    main()
