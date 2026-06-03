---
name: add-manual
description: Ingests a single PDF manual into the knowledge base with validation and search verification. Use when adding a new owner's manual PDF to the system. Triggers on "add this manual", "ingest this PDF", "index a new manual".
---

# Add Manual

Ingests a single PDF into the SQLite FTS5 knowledge base. Validates the file, extracts text with pypdf or marker, chunks by heading, and verifies the content is searchable.

## How It Works

1. **Validate** — Confirm the PDF exists and is readable
2. **Choose extractor** — `pypdf` (fast, no deps) or `marker` (heading-aware, requires `marker-pdf`)
3. **Ingest** — Run `ingest_pdf()` which extracts, chunks by ATX headings, and inserts into SQLite with FTS5 triggers
4. **Verify** — Run a search query matching the filename or content to confirm chunks landed
5. **Report** — Present filename, category, section count, and a sample search result

## Usage

```bash
bash .opencode/skills/add-manual/scripts/add-manual.sh --file manuals/foo.pdf [--category Automotive] [--extractor pypdf|marker]
```

**Arguments:**
- `--file` (required) — Path to the PDF
- `--category` (optional) — e.g. Automotive, Appliances (default: none)
- `--extractor` (optional) — `pypdf` (default) or `marker`
- `--max-pages` (optional) — Limit to first N pages (saves RAM)

**Examples:**
```bash
# Quick ingest with pypdf
bash .opencode/skills/add-manual/scripts/add-manual.sh --file manuals/AT6Z2323OM.pdf --category Automotive

# Full-quality ingest with marker for complex layouts
bash .opencode/skills/add-manual/scripts/add-manual.sh --file manuals/ab2100d.pdf --extractor marker

# Test with first 10 pages only
bash .opencode/skills/add-manual/scripts/add-manual.sh --file manuals/big.pdf --max-pages 10
```

## Output

```
✓ manuals/foo.pdf → 24 sections ingested (category: Automotive)
✓ Verification: "foo" returned 24 results
```

## Present Results to User

Show the user:
- File name and category
- Number of sections ingested
- Verification search result count
- Any warnings (no category, fallback to pypdf, truncated pages)

## Troubleshooting

- **"No content sections found"** — The PDF may be image-only or use non-ATX headings. Try `--extractor marker`.
- **"Marker not found"** — Install with `uv sync --group dev --extra ingest`.
- **"PDF not found"** — Check the path. Place PDFs in `manuals/` or provide an absolute path.
- **"Timed out"** — Marker can take 10+ minutes on large PDFs. Use `--max-pages 50` to test first.
