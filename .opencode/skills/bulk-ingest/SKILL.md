---
name: bulk-ingest
description: Batch-ingests all unindexed PDFs from the manuals/ directory. Use when adding multiple manuals at once, setting up a fresh knowledge base, or re-indexing after clearing the database. Triggers on "ingest all PDFs", "batch ingest", "import all manuals".
---

# Bulk Ingest

Scans the `manuals/` directory for PDFs, diffs against already-indexed documents in the database, and ingests each new one with pypdf. Collects per-file results into a summary report.

## How It Works

1. **Scan** — List all `.pdf` files in `manuals/`
2. **Diff** — Query the `documents` table for already-indexed filenames
3. **Ingest** — For each unindexed PDF, run `ingest_pdf()` with pypdf (fast, no deps) and no category
4. **Report** — Print a summary table with per-file status, section count, and any errors

The script does **not** stop on a single failure — it logs the error and continues with the next file.

## Usage

```bash
bash .opencode/skills/bulk-ingest/scripts/bulk-ingest.sh
```

**No arguments needed.** The script uses the default database path and scans `manuals/` automatically.

**Environment variables:**
- `DATABASE_PATH` — Override the default DB location

**Examples:**
```bash
# Ingest everything
bash .opencode/skills/bulk-ingest/scripts/bulk-ingest.sh

# Use a different database
DATABASE_PATH=/tmp/test.db bash .opencode/skills/bulk-ingest/scripts/bulk-ingest.sh
```

## Output

```
Found 5 PDFs in manuals/
Already indexed: 2
New: 3

Processing manuals/washer.pdf ... Done (18 sections)
Processing manuals/dryer.pdf ... Done (12 sections)
Processing manuals/oven.pdf ... Error: No content sections found

Summary:
  Total: 3 | Success: 2 | Failed: 1
  Sections added: 30
```

## Present Results to User

Show the user:
- How many PDFs were found vs. already indexed
- Per-file results (success/failure, section count)
- Summary counts
- Any failed files with error details

## Troubleshooting

- **All PDFs show "already indexed"** — The DB already has them. Run with a fresh DB or delete them first.
- **Image-only PDFs fail** — pypdf can't extract text from images. Use the `add-manual` skill with `--extractor marker` for those.
- **No PDFs found** — Place PDFs in `manuals/` and try again.
