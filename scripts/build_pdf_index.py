#!/usr/bin/env python3
"""Build a resumable, page-level text/OCR index for one exact PDF file."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover - exercised by installation errors
    raise SystemExit("Missing dependency: install with 'python -m pip install -r requirements.txt'.") from exc


SENSITIVE_PATTERNS = (
    (re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?!\w)"), "[EMAIL REDACTED]"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[PHONE REDACTED]"),
    (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "[ID REDACTED]"),
    (re.compile(r"(?<!\d)\d{16,19}(?!\d)"), "[ACCOUNT REDACTED]"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def meaningful_count(text: str) -> int:
    return len(re.findall(r"[\w\u3400-\u9fff]", text, flags=re.UNICODE))


def looks_garbled(text: str) -> bool:
    if not text:
        return False
    replacement = text.count("\ufffd")
    controls = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    return (replacement + controls) / max(len(text), 1) > 0.03


def redact(text: str) -> str:
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def parse_page_spec(value: str) -> set[int]:
    pages: set[int] = set()
    if not"value.strip():
        return pages
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            left, right = token.split("-", 1)
            start, end = int(left), int(right)
            if start < 1 or end < start:
                raise argparse.ArgumentTypeError(f"Invalid page range: {token}")
            pages.update(range(start, end + 1))
        else:
            page = int(token)
            if page < 1:
                raise argparse.ArgumentTypeError(f"Invalid page: {token}")
            pages.add(page)
    return pages


def load_json(path: Path | None, default: Any) -> Any:
    if path is None:
        return default
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate_sections(items: list[dict[str, Any]], page_count: int) -> list[dict[str, Any]]:
    normalized = []
    occupied: set[int] = set()
    for item in items:
        start, end, name = int(item["start"]), int(item["end"]), str(item["name"]).strip()
        if start < 1 or end < start or end > page_count or not name:
            raise SystemExit(f"Invalid section entry: {item}")
        page_set = set(range(start, end + 1))
        overlap = occupied & page_set
        if overlap:
            raise SystemExit(f"Section ranges overlap at page {min(overlap)}")
        occupied.update(page_set)
        normalized.append({"start": start, "end": end, "name": name})
    return normalized


def section_for(page: int, sections: list[dict[str, Any]]) -> str:
    for item in sections:
        if item["start"] <= page <= item["end"]:
            return item["name"]
    return ""


def load_rows(path: Path) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                rows[int(row["page"])] = row
            except Exception as exc:
                raise SystemExit(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return rows


def run_ocr(
    pdf_path: Path,
    page_number: int,
    dpi: int,
    language: str,
    pdftoppm: str,
    tesseract: str,
) -> str:
    with tempfile.TemporaryDirectory(prefix="pdf-evidence-ocr-") as temp_dir:
        prefix = Path(temp_dir) / "page"
        render = subprocess.run(
            [
                pdftoppm,
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-r",
                str(dpi),
                "-png",
                "-singlefile",
                str(pdf_path),
                str(prefix),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if render.returncode != 0:
            raise RuntimeError(render.stderr.strip() or "pdftoppm failed")
        image_path = prefix.with_suffix(".png")
        ocr = subprocess.run(
            [tesseract, str(image_path), "stdout", "-l", language, "--psm", "6"],
            check=False,
            capture_output=True,
            text=True,
        )
        if ocr.returncode != 0:
            raise RuntimeError(ocr.stderr.strip() or "tesseract failed")
        return ocr.stdout.strip()


def write_jsonl(path: Path, rows: dict[int, dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for page in sorted(rows):
            stream.write(json.dumps(rows[page], ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="PDF to index")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for index files")
    parser.add_argument("--password", default=None, help="PDF password, if required")
    parser.add_argument("--ocr", choices=("auto", "always", "never"), default="auto")
    parser.add_argument("--ocr-pages", type=parse_page_spec, default=set(), help="Force OCR, e.g. 1-3,8,10")
    parser.add_argument("--ocr-language", default="chi_sim+eng", help="Tesseract language expression")
    parser.add_argument("--ocr-dpi", type=int, default=220)
    parser.add_argument("--min-meaningful-chars", type=int, default=80)
    parser.add_argument("--section-map", type=Path, help="Optional section-map JSON")
    parser.add_argument("--notes", type=Path, help="Optional page-note JSON object")
    parser.add_argument("--resume", action="store_true", help="Resume a matching partial or completed index")
    parser.add_argument(
        "--redact-sensitive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Redact common email, phone, ID, and account patterns (default: true)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path = args.pdf.expanduser().resolve()
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    meta_path = output_dir / "index_meta.json"
    final_path = output_dir / "pages.jsonl"
    partial_path = output_dir / "pages.partial.jsonl"

    checksum = sha256_file(pdf_path)
    reader = PdfReader(str(pdf_path), password=args.password)
    page_count = len(reader.pages)
    forced_pages = set(args.ocr_pages)
    invalid_forced = [page for page in forced_pages if page > page_count]
    if invalid_forced:
        raise SystemExit(f"OCR page exceeds PDF page count: {min(invalid_forced)} > {page_count}")

    sections = validate_sections(load_json(args.section_map, []), page_count)
    raw_notes = load_json(args.notes, {})
    if not isinstance(raw_notes, dict):
        raise SystemExit("Notes file must be a JSON object keyed by page number")
    notes = {int(page): str(note) for page, note in raw_notes.items()}

    meta = {
        "source_name": pdf_path.name,
        "source_path": str(pdf_path),
        "source_bytes": pdf_path.stat().st_size,
        "sha256": checksum,
        "page_count": page_count,
        "page_numbering": "1-based PDF viewer page order including covers",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "ocr_mode": args.ocr,
        "ocr_language": args.ocr_language,
        "sensitive_data_redacted": args.redact_sensitive,
    }

    existing_meta = load_json(meta_path, None) if meta_path.exists() else None
    if existing_meta and (
        existing_meta.get("sha256") != checksum or existing_meta.get("page_count") != page_count
    ):
        raise SystemExit("Output directory belongs to a different PDF version; choose a new directory.")

    existing_source = partial_path if partial_path.exists() else final_path
    if existing_source.exists() and not args.resume:
        raise SystemExit("Index output already exists; use --resume or choose a new output directory.")
    rows = load_rows(existing_source) if args.resume else {}

    pdftoppm = shutil.which("pdftoppm")
    tesseract = shutil.which("tesseract")
    if (args.ocr == "always" or forced_pages) and (not pdftoppm or not tesseract):
        raise SystemExit("OCR requested but pdftoppm or tesseract is not installed.")
    if args.ocr == "auto" and (not pdftoppm or not tesseract):
        print("Warning: OCR tools unavailable; sparse pages will keep extracted text only.", file=sys.stderr)

    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_jsonl(partial_path, rows)

    with partial_path.open("a", encoding="utf-8") as stream:
        for page_number, page in enumerate(reader.pages, 1):
            if page_number in rows:
                continue
            extraction_error = ""
            try:
                extracted = (page.extract_text() or "").strip()
            except Exception as exc:  # malformed PDFs should still produce an index row
                extracted = ""
                extraction_error = str(exc)

            extracted_chars = meaningful_count(extracted)
            should_ocr = (
                args.ocr == "always"
                or page_number in forced_pages
                or (
                    args.ocr == "auto"
                    and (extracted_chars < args.min_meaningful_chars or looks_garbled(extracted))
                )
            )
            ocr_text = ""
            ocr_error = ""
            if should_ocr and pdftoppm and tesseract:
                try:
                    ocr_text = run_ocr(
                        pdf_path,
                        page_number,
                        args.ocr_dpi,
                        args.ocr_language,
                        pdftoppm,
                        tesseract,
                    )
                except Exception as exc:
                    ocr_error = str(exc)

            if ocr_text and (should_ocr or meaningful_count(ocr_text) > extracted_chars):
                chosen_text, source = ocr_text, "ocr"
            else:
                chosen_text, source = extracted, "extracted"
            if args.redact_sensitive:
                chosen_text = redact(chosen_text)

            row = {
                "page": page_number,
                "section": section_for(page_number, sections),
                "text_source": source,
                "extracted_chars": extracted_chars,
                "ocr_chars": meaningful_count(ocr_text),
                "manual_note": notes.get(page_number, ""),
                "text": chosen_text,
            }
            if extraction_error:
                row["extraction_error"] = extraction_error
            if ocr_error:
                row["ocr_error"] = ocr_error
            rows[page_number] = row
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            if page_number == 1 or page_number % 25 == 0 or page_number == page_count:
                print(f"Indexed page {page_number}/{page_count}", file=sys.stderr)

    for page, row in rows.items():
        row["section"] = section_for(page, sections)
        row["manual_note"] = notes.get(page, row.get("manual_note", ""))
    write_jsonl(final_path, rows)
    partial_path.unlink(missing_ok=True)
    print(final_path)


if __name__ == "__main__":
    main()
