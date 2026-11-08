# Index files and schemas

## `index_meta.json`

Records source identity and indexing settings:

```json
{
  "source_name": "packet.pdf",
  "source_path": "/absolute/path/packet.pdf",
  "sha256": "...",
  "page_count": 661,
  "page_numbering": "1-based PDF viewer page order including covers",
  "ocr_mode": "auto",
  "ocr_language": "chi_sim+eng",
  "sensitive_data_redacted": true
}
```

## `pages.jsonl`

One JSON object per PDF page:

```json
{
  "page": 14,
  "section": "Applicant institution evidence",
  "text_source": "ocr",
  "extracted_chars": 0,
  "ocr_chars": 836,
  "manual_note": "Government article about an implanted BCI procedure",
  "text": "..."
}
```

`text` is searchable navigation text. `manual_note` is a short human-verified locator, not a replacement transcription.

## Section map

An optional JSON array of inclusive page ranges:

```json
[
  {"start": 1, "end": 14, "name": "Applicant institution evidence"}
]
```

Ranges may be discontinuous but must not overlap. Pages outside all ranges receive an empty section.

## Page notes

An optional JSON object mapping page numbers to concise notes:

```json
{"14": "Article heading and procedure photograph"}
```

Do not place confidential data in notes intended for sharing.
