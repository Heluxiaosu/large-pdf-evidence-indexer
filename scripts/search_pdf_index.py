#!/usr/bin/env python3
"""Rank likely PDF pages for a passage or distinctive evidence phrase."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


def normalize(value: str) -> str:
    return "".join(re.findall(r"[\u3400-\u9fffA-Za-z0-9]+", value)).lower()


def grams(value: str, size: int) -> set[str]:
    return {value[index : index + size] for index in range(max(0, len(value) - size + 1))}


def parse_page_spec(value: str) -> set[int]:
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
    return pages


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSONL at line {line_number}: {exc}") from exc
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path, help="pages.jsonl from build_pdf_index.py")
    parser.add_argument("query", help="Full passage or distinctive phrase")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--within", type=parse_page_spec, help="Restrict to pages, e.g. 1-226")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_rows(args.index.expanduser().resolve())
    if args.within:
        rows = [row for row in rows if int(row["page"]) in args.within]

    query = normalize(args.query)
    if len(query) < 2:
        raise SystemExit("Query is too short after normalization")
    size = 2 if len(query) < 8 else 3 if len(query) < 18 else 4
    query_grams = grams(query, size)
    documents = [normalize((row.get("manual_note") or "") + "\n" + (row.get("text") or "")) for row in rows]
    document_grams = [grams(document, size) for document in documents]
    frequencies = Counter(gram for group in document_grams for gram in group if gram in query_grams)

    ranked = []
    for row, document, group in zip(rows, documents, document_grams):
        matched = query_grams & group
        if not matched:
            continue
        score = sum(math.log((len(rows) + 1) / (frequencies[gram] + 1)) + 1 for gram in matched)
        coverage = len(matched) / max(len(query_grams), 1)
        score *= 0.5 + coverage
        if len(query) >= 6 and query in document:
            score *= 1.75
        preview_source = row.get("manual_note") or row.get("text") or ""
        preview = re.sub(r"\s+", " ", preview_source).strip()[:180]
        ranked.append(
            {
                "page": int(row["page"]),
                "score": round(score, 2),
                "coverage": round(coverage, 3),
                "matched_grams": len(matched),
                "section": row.get("section", ""),
                "preview": preview,
            }
        )

    ranked.sort(key=lambda item: (-item["score"], item["page"]))
    selected = ranked[: args.top]
    if args.json:
        print(json.dumps(selected, ensure_ascii=False, indent=2))
        return
    for item in selected:
        section = f"\t{item['section']}" if item["section"] else ""
        print(
            f"Page {item['page']}\t{item['score']:.2f}\tcoverage={item['coverage']:.1%}"
            f"{section}\t{item['preview']}"
        )


if __name__ == "__main__":
    main()
