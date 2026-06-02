# Implementation Plan: Local-First Layout-Aware Manual Assistant

## Overview

A Python MCP server + companion web UI that indexes owner's manual PDFs and answers natural language questions using FTS5 retrieval + cloud LLMs. Single-user, terminal-driven via OpenCode, with a browser fallback for browsing search results.

## Architecture Decisions

- **Python package** (`manuals_app/`) with shared search module — both MCP server and web UI import the same query logic
- **FTS5 query sanitization** — user queries are sanitized (FTS5 special chars `"*+()^~:` stripped); FTS5 implicit AND (space-separated terms) is used instead of phrase wrapping
- **Heading-only chunking** — split on any ATX heading (`^#{1,} `), no max size cap; preamble and postamble content captured under generated heading paths
- **Code-block awareness** — fenced code blocks tracked during splitting to avoid false `#` matches
- **WAL mode** — SQLite WAL journaling for concurrent-read safety during ingest
- **No generation in web UI** — web page returns raw chunks for manual browsing; LLM synthesis is only in OpenCode
- **Structured LLM prompt** — chunks labeled by filename + heading path, with explicit "answer from context only" instruction
- **Marker as optional dependency** — `marker-pdf` (with torch/detectron2) is behind `[ingest]` extra to avoid heavy builds on every install

## Project Structure

```
~/Dev/owners-manual-assistant/
├── pyproject.toml
├── README.md
├── AGENTS.md
├── CHANGELOG.md
├── LICENSE
├── .github/workflows/ci.yml
├── manuals_knowledge.db   (gitignored)
├── manuals_app/
│   ├── __init__.py
│   ├── db.py               -- connection, schema, triggers
│   ├── search.py           -- shared FTS5 search logic
│   ├── ingest.py           -- CLI: PDF ingestion entry point
│   ├── mcp_server.py       -- MCP SDK server entry point
│   └── web_ui.py           -- FastAPI search UI
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_db.py
│   ├── test_search.py
│   ├── test_ingest.py
│   ├── test_web_ui.py
│   └── test_mcp_server.py
└── .gitignore
```

## Task List

### Task 1: Project Scaffolding

**Description:** Create the Python package structure, dependency declarations, `.gitignore`, and venv setup.

**Acceptance criteria:**
- [ ] `pyproject.toml` declares dependencies: `mcp`, `fastapi`, `uvicorn`, `jinja2` as base deps
- [ ] `marker-pdf` is declared under `[project.optional-dependencies]` as `ingest` extra
- [ ] `pytest` is declared under `[project.optional-dependencies]` as `dev` extra
- [ ] `manuals_app/` package with `__init__.py`
- [ ] `tests/` package with `__init__.py`
- [ ] `.gitignore` excludes `*.db`, `__pycache__/`, `*.egg-info/`, `venv/`, `output_dir/` (Marker output)
- [ ] `python -m venv .venv && source .venv/bin/activate && pip install -e .` works cleanly (no heavy deps)

**Verification:**
- [ ] `pip install -e ".[dev]"` completes
- [ ] `pip install -e ".[ingest]"` completes (installs torch/detectron2)
- [ ] `python -c "from manuals_app import db"` succeeds

**Dependencies:** None

**Files touched:**
- `pyproject.toml` (new)
- `.gitignore` (new)
- `manuals_app/__init__.py` (new)
- `tests/__init__.py` (new)

**Estimated scope:** Small (2-3 files)

---

### Task 2: Database Module

**Description:** Implement `db.py` — SQLite connection management (with WAL mode), schema creation for `documents`, `document_chunks`, and `chunks_fts` with FTS5 sync triggers.

**Acceptance criteria:**
- [ ] `init_db(db_path)` creates all tables and triggers on first call
- [ ] `get_connection(db_path)` returns a connection with row factory enabled
- [ ] WAL mode is enabled on the connection: `PRAGMA journal_mode=WAL;`
- [ ] Schema matches spec exactly (documents, document_chunks, chunks_fts, 3 triggers)
- [ ] Running `init_db` on an existing database is idempotent (uses `IF NOT EXISTS`)
- [ ] `DATABASE_PATH` env var is resolved to an absolute path before use

**Verification:**
- [ ] Manual: create DB, inspect with `.schema`, verify WAL mode via `PRAGMA journal_mode;`
- [ ] Insert document + chunks, verify FTS triggers populate `chunks_fts` automatically

**Dependencies:** Task 1

**Files touched:**
- `manuals_app/db.py` (new)

**Estimated scope:** Small (1 file)

---

### Task 3: Shared Search Module

**Description:** Implement `search.py` — parameterized FTS5 query builder with query sanitization, result formatting with structured context for LLM injection.

**Acceptance criteria:**
- [ ] `search_manuals(db_path, query, category=None, limit=5)` accepts user query, optional category filter, and result limit
- [ ] FTS5 special chars (`"`, `*`, `+`, `(`, `)`, `^`, `~`, `:`) are stripped from query
- [ ] FTS5 `MATCH` is wrapped in `try/except sqlite3.OperationalError` — returns `[]` gracefully
- [ ] Returns list of `{filename, category, heading_path, content_markdown}` dicts
- [ ] Results ordered by FTS5 rank, limited to `limit` param (default 5)
- [ ] Category filter uses `WHERE (? IS NULL OR category = ?)` — both params are the same value
- [ ] Empty results return empty list (caller handles the "no results" message)
- [ ] Function is importable by both MCP server and web UI
- [ ] `format_context(results)` returns labeled string: one section per chunk with filename + heading_path header; handles both null and empty category

**Verification:**
- [ ] `pytest tests/` passes
- [ ] Manual: insert sample chunks, run search, verify correct chunks returned
- [ ] Search with no matches returns `[]`
- [ ] Category filter returns only matching documents
- [ ] Query containing FTS5 special chars (`*`, `(`, etc.) does not crash

**Dependencies:** Task 2

**Files touched:**
- `manuals_app/search.py` (new)

**Estimated scope:** Small (1 file)

---

### Task 4: Ingestion Pipeline

**Description:** Implement `ingest.py` — CLI script that takes a PDF path and optional category, runs Marker, chunks by heading (any depth), captures preamble/postamble, tracks code blocks, strips image references, cleans up media, stores in DB.

**Acceptance criteria:**
- [ ] `python -m manuals_app.ingest --file manual.pdf` runs Marker and stores results
- [ ] `python -m manuals_app.ingest --file manual.pdf --category Automotive` stores with category
- [ ] Chunks are split on any ATX heading (`^#{1,} ` at line start)
- [ ] Fenced code blocks (triple backtick) are tracked to avoid false `#` matches inside them
- [ ] Content before the first heading is stored under `heading_path = "(preamble)"`
- [ ] Content after the last heading is stored under `heading_path = "(postamble)"`
- [ ] Tables inside headings are preserved intact
- [ ] Image references — both inline (`![...](...)`) and reference-style (`![alt][ref]` + `[ref]: url`) — are stripped from chunks
- [ ] `heading_path` accumulates the heading hierarchy (e.g. `"Maintenance > Oil Change"`)
- [ ] Document record and chunks are inserted in a transaction (no partial state on crash)
- [ ] Marker's generated media directory is cleaned up after ingestion (temp directory pattern)
- [ ] Marker failures (crash, password-protected PDF, corrupt file) raise a clear error; partial output is discarded
- [ ] FTS index auto-populates via triggers

**Verification:**
- [ ] Run on a sample PDF, verify correct number of chunks in DB
- [ ] Verify heading_path is correct for nested headings
- [ ] Verify preamble and postamble content are stored
- [ ] Verify content inside fenced code blocks containing `#` does not trigger false splits
- [ ] Verify image references (both styles) are absent from stored content
- [ ] Verify table rows survived the round-trip
- [ ] Verify no Marker media files remain after ingestion
- [ ] Verify error on a password-protected PDF is reported cleanly

**Dependencies:** Task 1 (pip install -e ".[ingest]"), Task 2

**Files touched:**
- `manuals_app/ingest.py` (new)

**Estimated scope:** Medium (3-5 files — ingest.py plus supporting helpers if needed)

---

### Task 5: MCP Server

**Description:** Implement `mcp_server.py` — Python MCP SDK server exposing the `search_manuals` tool. OpenCode registration documented in README.

**Acceptance criteria:**
- [ ] Server starts and registers with `search_manuals` tool on stdio transport
- [ ] Tool signature: `search_manuals(query: str, category: str | None = None) -> str`
- [ ] Returns formatted context with chunks labeled by filename + heading path
- [ ] Returns `"I couldn't find relevant information in your manuals."` when no results
- [ ] DATABASE_PATH from env var, fallback to `./manuals_knowledge.db`
- [ ] Server responds to MCP ping/initialize lifecycle correctly
- [ ] OpenCode config snippet in README matches the correct format

**Verification:**
- [ ] `python -m manuals_app.mcp_server` starts without error
- [ ] Manual: test with `mcp-cli` or `opencode` inspector tool
- [ ] Verify tool returns correct results for known queries

**Dependencies:** Task 3, Task 2

**Files touched:**
- `manuals_app/mcp_server.py` (new)
- `README.md` (update with config)

**Estimated scope:** Medium (2 files)

---

### Task 6: Web UI

**Description:** Implement `web_ui.py` — minimal FastAPI app with a search form and results page displaying raw chunks. Includes Jinja2 HTML templates.

**Acceptance criteria:**
- [ ] `GET /` renders a search form with query input and optional category dropdown
- [ ] `GET /search?q=...&category=...` returns results page with matching chunks
- [ ] Each result shows: filename, heading path, content markdown
- [ ] Results grouped by filename for multi-manual queries
- [ ] No LLM generation call — just search results for manual browsing
- [ ] Served on `http://localhost:8080` by default
- [ ] No JavaScript dependency — pure HTML + Jinja2 templates
- [ ] Two templates created: `templates/search.html` (form) and `templates/results.html` (results)

**Verification:**
- [ ] `python -m manuals_app.web_ui` starts and is accessible at `localhost:8080`
- [ ] Search returns correctly grouped results
- [ ] Empty search returns "no results" page
- [ ] Category filter narrows results

**Dependencies:** Task 3, Task 2

**Files touched:**
- `manuals_app/web_ui.py` (new)
- `manuals_app/templates/search.html` (new)
- `manuals_app/templates/results.html` (new)

**Estimated scope:** Medium (3 files)

---

### Task 7: Tests

**Description:** Automated tests for the search module and ingestion pipeline.

**Acceptance criteria:**
- [ ] `test_search_query_building` — verifies phrase wrapping, internal quote stripping, category filtering
- [ ] `test_search_empty_results` — verifies empty list for non-matching queries
- [ ] `test_search_with_category` — verifies category filter narrows results
- [ ] `test_search_internal_quotes` — verifies query with `"` does not crash and returns expected results
- [ ] `test_format_context` — verifies structured LLM context formatting
- [ ] `test_chunk_heading_path` — verifies heading hierarchy accumulation
- [ ] `test_chunk_preamble_postamble` — verifies content before first and after last heading is captured
- [ ] `test_chunk_image_stripping` — verifies both inline and reference-style images removed
- [ ] `test_chunk_code_block_awareness` — verifies `#` inside fenced code blocks does not trigger split
- [ ] Tests use a temporary in-memory SQLite database (not production DB)
- [ ] `pytest tests/` runs clean with no failures

**Verification:**
- [ ] `pytest tests/ -v` passes
- [ ] Code coverage of search module is >80%

**Dependencies:** Task 3, Task 4

**Files touched:**
- `tests/test_search.py` (new)
- `tests/conftest.py` (optional, shared fixtures)

**Estimated scope:** Small (1-2 files)

---

### Task 8: Documentation

**Description:** Write README.md with complete setup instructions, ingestion guide, MCP registration, and web UI usage.

**Acceptance criteria:**
- [ ] README documents: project overview, prerequisites (Python 3.10+, Marker's torch/detectron2 requirements)
- [ ] Setup instructions: venv creation, `pip install -e .` (base), `pip install -e ".[ingest]"` (with Marker), `pip install -e ".[dev]"` (with pytest)
- [ ] Ingestion usage: `python -m manuals_app.ingest --file manual.pdf --category Automotive`
- [ ] MCP server startup and OpenCode config snippet (matching spec's `$schema` format)
- [ ] Web UI startup and access instructions
- [ ] OpenCode config snippet in the exact `$schema` format from spec
- [ ] Troubleshooting section for common Marker issues (CUDA, torch, detectron2)

**Verification:**
- [ ] README renders correctly on GitHub
- [ ] A new developer can follow the guide without external references

**Dependencies:** Task 5, Task 6

**Files touched:**
- `README.md` (new)

**Estimated scope:** Small (1 file)

---

## Checkpoints

### Checkpoint 1: After Tasks 1-3 (Foundation)
- [ ] `pip install -e .` installs cleanly
- [ ] DB schema creates correctly
- [ ] Search module returns correct results for test queries
- [ ] Review with human before proceeding

### Checkpoint 2: After Tasks 4-5 (Core Features)
- [ ] Ingest a sample PDF end-to-end
- [ ] MCP server responds to queries correctly
- [ ] OpenCode can invoke the tool
- [ ] Review with human before proceeding

### Checkpoint 3: After Tasks 6-8 (Polish)
- [ ] Web UI renders search results
- [ ] `pytest tests/` passes
- [ ] README documents setup and usage
- [ ] Ready for review

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Marker's torch/detectron2 deps are painful to install (CUDA mismatch, etc.) | High | Moved to `[ingest]` extra so base install is lightweight; document exact install steps in README |
| FTS5 implicit AND may miss results for complex multi-word queries | Medium | User can rephrase; upgrade to prefix/BM25 later if needed |
| PDF layout is too complex for Marker (dense tables, weird columns) | Medium | Verify with a real PDF early in Task 4; Marker has a `--langs` flag that may help |
| sqlite FTS5 not available in system Python's sqlite3 | Low | Python 3.10+ bundles FTS5; verify in Task 2 |
| Concurrent ingest + query hits `SQLITE_BUSY` | Low | WAL mode in Task 2 enables concurrent reads during writes |

## Open Questions

- None resolved — spec and plan cover all decisions
