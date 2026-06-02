# Owner's Manual Assistant
![CI](https://github.com/AndyN9/owners-manual-assistant/actions/workflows/ci.yml/badge.svg)

Local-first, layout-aware owner's manual assistant with FTS5 retrieval + cloud LLM.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- (Optional) CUDA-compatible GPU for Marker extractor — skipped when using the default pypdf extractor.

## Setup

```bash
uv sync --group dev                 # base + dev (testing)
uv sync --group dev --extra ingest  # add marker-pdf for PDF ingestion
```

## Ingestion

Place PDFs in the `manuals/` directory, then:

```bash
uv run python -m manuals_app.ingest --file manuals/manual.pdf --category Automotive
```

Extracts text via pypdf (fast, low memory). For better heading-aware extraction:

```bash
uv run python -m manuals_app.ingest --file manuals/manual.pdf --category Automotive --extractor marker
```

Each call ingests one PDF. Heading-chunks and inserts into SQLite with FTS5 full-text search indexed.

## Search

### MCP Server (stdio)

```bash
uv run python -m manuals_app.mcp_server
```

Registers a `search_manuals` tool. OpenCode/Claude Code auto-discovers via the stdio transport.

Arguments:
- `query` (str) — search terms
- `category` (str, optional) — filter by category

**Project-level registration** (optional): `.opencode/opencode.json` declares the server so OpenCode launches it automatically when needed. Add a `DATABASE_PATH` environment variable there if you customize the DB location.

### Web UI

```bash
uv run python -m manuals_app.web_ui
```

Opens on `http://localhost:8080`. Form-based search with grouped-by-document results.

## Environment

- `DATABASE_PATH` — path to SQLite DB (default: `./manuals_knowledge.db`)

## Tests

```bash
uv run pytest tests/
```

## Project Structure

```
manuals/          — place PDFs here for ingestion (ignored by git)
manuals_app/
  db.py           — connection, schema, FTS5 triggers
  search.py       — FTS5 query builder, sanitization, context formatting
  ingest.py       — CLI ingest with Marker + heading chunking
  mcp_server.py   — MCP stdio server with search_manuals tool
  web_ui.py       — FastAPI web interface
  templates/      — Jinja2 templates (search form, results)
tests/
  conftest.py        — fixtures (temp DB, populated DB)
  test_db.py         — schema, triggers, WAL mode
  test_search.py     — sanitize, search, format_context, FTS5 error handling
  test_ingest.py     — CLI arg validation, strip_images, parse_markdown_sections
  test_web_ui.py     — FastAPI TestClient (form, results, validation)
  test_mcp_server.py — create_app returns Server
```

## License

MIT License. See [LICENSE](LICENSE).
