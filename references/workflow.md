# Evidence indexing workflow

## 1. Freeze the source identity

Large application packets are often revised by inserting or replacing pages. A page number is valid only for one exact file. Store:

- original filename and absolute path used during indexing;
- SHA-256 checksum;
- total PDF pages;
- 1-based viewer numbering convention;
- creation time of the index;
- OCR mode and language.

If the checksum changes, build a new index directory. Do not patch old page offsets by hand.

## 2. Extract before OCR

Use embedded PDF text when it is meaningful. OCR is slower and introduces substitutions in names, dates, symbols, tables, and document numbers. Automatic OCR is appropriate when a page has little usable extracted text or obvious decoding damage. Force OCR for known scan ranges with `--ocr-pages`.

The index is deliberately a navigation aid. It should help locate likely pages quickly; it should not be treated as a certified transcription.

## 3. Add section context

For packets with covers and repeated subsections, create a JSON section map:

```json
[
  {"start": 1, "end": 14, "name": "Applicant institution evidence"},
  {"start": 15, "end": 226, "name": "Program construction evidence"}
]
```

Pass it with `--section-map sections.json`. Section names improve search output and help prevent confusing repeated evidence from different appendices.

Optional manual notes can capture visually confirmed headings without rewriting the source. Use a JSON object keyed by page number:

```json
{
  "14": "Government article about an implanted brain-computer-interface procedure",
  "68": "National first-class undergraduate program list; clinical medicine entry"
}
```

Pass it with `--notes page-notes.json`.

## 4. Retrieve with multiple anchors

For a long form paragraph:

1. Search the whole passage for overall candidates.
2. Search rare anchors separately: names, award titles, years, course names, approval numbers, and uncommon technical phrases.
3. Compare repeated copies and prefer the page that directly shows the issuing authority, certificate, list entry, or source heading.
4. Render adjacent pages when a table or notice continues across pages.

## 5. Verify the original page image

Before returning final page numbers, confirm:

- the named person or institution is the same entity;
- award/project level and year match;
- list row, certificate, or notice is visible rather than inferred;
- page numbering matches the viewer, including covers;
- a multi-page table has not split the heading from the relevant row;
- OCR has not changed a name, digit, or symbol.

When the user requests only page numbers, perform this verification silently and return only those numbers.

## 6. Handle unsupported or planned content

Application text often mixes existing facts with proposed targets. Existing platform certificates, appointment records, curricula, awards, and agreements can have evidence pages. Future targets such as planned team size, training counts, annual assessment, or intended outputs usually do not have historical evidence pages.

Do not assign unrelated pages to planned targets. If explanation is allowed, distinguish:

- directly supported facts;
- background pages that establish feasibility;
- planned actions that belong to the application narrative rather than the evidence packet.

## 7. Privacy and sharing

The default index redacts common phone, email, Chinese ID, and bank-card patterns. Keep raw PDFs and rendered pages out of public repositories unless publication is authorized. A reusable skill repository should contain scripts and synthetic examples only, never the user's source packet or generated index.
