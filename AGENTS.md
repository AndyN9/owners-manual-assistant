# AGENTS.md - Owner's Manual Assistant

Guidance for AI coding agents working on this repository.

## Project Overview

Local-first owner's manual assistant. Ingests PDF manuals via Marker, chunks by headings, indexes with SQLite FTS5, and exposes search through an MCP server (stdio) and a FastAPI web UI.

## Architecture

```
PDF → Marker → heading-chunker → SQLite (FTS5) ← search_manuals() → MCP server / Web UI
```

Three layers:
- **Storage** (`db.py`): SQLite with WAL mode, `documents`/`document_chunks` tables, FTS5 virtual table with sync triggers
- **Search** (`search.py`): FTS5 query builder, sanitization (strips FTS5 special chars: `"*+()^~:`), `format_context()` for structured LLM output
- **Entry points**: `ingest.py` (CLI), `mcp_server.py` (stdio MCP), `web_ui.py` (FastAPI)

## Key Constraints

- Cloud LLM only — no local models or embeddings
- FTS5 keyword search, not vector search — no embedding provider
- Single-user, single-machine — no auth, no multi-tenancy
- One PDF at a time — no batch ingestion in v1
- Web UI displays raw FTS5 results only — no LLM generation call in the UI
- Marker dependency behind `[ingest]` extra — tests and base install must not require it

## Code Conventions

- Python 3.10+ with `str | None` union syntax (no `Optional`)
- FastAPI + Jinja2 for web UI, MCP SDK v1 for MCP server
- Standard library `pathlib.Path` for paths, `tempfile` for temp dirs
- `sqlite3.Row` as row factory, parameterized queries throughout
- Error handling: use `raise` for errors in library code, `sys.exit(1)` in CLI `main()`
- Tests: pytest with `conftest.py` fixtures, no test dependencies beyond `[dev]`
- No comments in code unless explaining a non-obvious design decision

## Critical Context for Agents

- MCP SDK v1 requires `app.run(read_stream, write_stream, app.create_initialization_options())` — `stdio_server()` yields `(read_stream, write_stream)`
- `conn.lastrowid` is unreliable — use `conn.execute('SELECT last_insert_rowid()').fetchone()[0]` instead
- FTS5 implicit AND (space-separated terms) is the default and works better than phrase wrapping — do not wrap user queries in double-quotes
- FTS5 is case-insensitive by default
- Starlette 1.2.1+ `TemplateResponse` signature is `(request, name, context)` — first positional is request, not template name
- Search sanitization (`_sanitize_query`) strips FTS5 special chars (`"`, `*`, `+`, `(`, `)`, `^`, `~`, `:`) via compiled regex. The `-` is preserved (useful for terms like "5W-30")
- FTS5 `MATCH` is wrapped in `try/except OperationalError` — returns `[]` gracefully on syntax errors
- Sync DB calls (`search_manuals`) are offloaded with `asyncio.to_thread()` in both MCP and web UI handlers
- `db_path` is resolved per-request (not captured at import time) to support test isolation and runtime reconfiguration
- Queries are truncated to `MAX_QUERY_LENGTH=200` in both web UI and MCP server
- Ingest heading stack is capped at `MAX_HEADING_DEPTH=20`; code fence detection handles `~` fences and 4+ backtick fences

## Development

```bash
uv sync --group dev                 # install
uv sync --group dev --extra ingest  # add marker-pdf
uv run pytest tests/ -v             # run tests
uv run python -m manuals_app.ingest --file manuals/foo.pdf  # test ingestion
uv run python -m manuals_app.web_ui      # test web UI at localhost:8080
```

## Module Map

| Module          | Responsibility                                                                                |
| --------------- | --------------------------------------------------------------------------------------------- |
| `db.py`         | Connection, WAL mode, CREATE TABLE/TRIGGER, `get_database_path()`                             |
| `search.py`     | `search_manuals()` FTS5 query, `format_context()` for LLM, `_sanitize_query()` FTS5 sanitizer |
| `ingest.py`     | CLI entry point, Marker subprocess, heading-chunking, `strip_images()`                        |
| `mcp_server.py` | `Server` with `list_tools`/`call_tool`, stdio transport, query length limit                   |
| `web_ui.py`     | FastAPI routes (`/` form, `/search` results), input validation (limit, max_length)            |

## Environment

- `DATABASE_PATH` — override default DB location (default: `./manuals_knowledge.db`)
