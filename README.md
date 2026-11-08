# Large PDF Evidence Indexer

A reusable Codex skill for finding and verifying evidence pages in very large, mixed text-and-scan PDF packets. It creates a version-specific page index, optionally OCRs sparse pages, searches long passages with character n-grams, and keeps the original-page verification step explicit.

The repository contains no source documents or user data.

Before publishing changes, run the repository safety audit. It rejects PDF files, generated JSONL indexes, index metadata, rendered-output directories, and unusually large files:

```bash
python scripts/audit_public_release.py .
```

The included workflow was tested with a synthetic PDF generated in a temporary directory. No test PDF is committed to this repository.

## Install as a Codex skill

Clone the repository into your Codex skills directory:

```bash
git clone https://github.com/Heluxiaosu/large-pdf-evidence-indexer.git \
  ~/.codex/skills/large-pdf-evidence-indexer
```

Then invoke it with `$large-pdf-evidence-indexer`, or let Codex select it automatically for large-PDF evidence lookup tasks.

## Runtime setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

For OCR, also install Poppler and Tesseract with the languages you need.

macOS:

```bash
brew install poppler tesseract tesseract-lang
```

Ubuntu/Debian:

```bash
sudo apt-get install poppler-utils tesseract-ocr tesseract-ocr-chi-sim
```

## Use the scripts directly

```bash
python scripts/build_pdf_index.py packet.pdf \
  --output-dir index-output \
  --ocr auto \
  --resume

python scripts/search_pdf_index.py index-output/pages.jsonl \
  "the paragraph or distinctive phrase to locate" \
  --top 20

python scripts/render_pdf_pages.py packet.pdf \
  --pages 12,14,64-68 \
  --output-dir index-output/rendered
```

Use `--section-map` and `--notes` when a packet needs named sections or human-verified navigation notes. See `references/output-schema.md` for the file formats.

## Design principles

- Page numbers belong to one exact PDF checksum and are never reused across versions.
- OCR and extracted text are search aids, not authoritative transcriptions.
- Final page references are checked against rendered original pages.
- Common contact and identity patterns are redacted from the index by default.
- The original PDF is never modified.
- Source PDFs, rendered pages, and generated indexes are excluded from Git and rejected by the release audit.

## License

MIT
