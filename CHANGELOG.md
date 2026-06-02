# Changelog

## 0.1.0 (unreleased)

### Features
- SQLite + FTS5 document storage with WAL mode
- PDF ingestion via Marker with heading-based chunking
- MCP server with `search_manuals` tool for Claude integration
- Web UI with grouped search results
- Python 3.10–3.12 support

### Fixes & Improvements
- FTS5 input sanitization strips all special chars (`"*+()^~:`) — prevents unbounded prefix searches
- FTS5 `MATCH` errors caught gracefully (returns empty results instead of 500)
- Sync DB calls offloaded with `asyncio.to_thread()` — doesn't block event loop
- `db_path` resolved per-request (not captured at import time) — enables test isolation
- Query length capped at 200 chars in both MCP and web UI
- Web UI enforces `limit` bounds (1–50) and rejects blank/oversized queries
- Ingest uses `executemany()` instead of per-chunk INSERTs
- Code fence detection handles `~` fences and 4+ backtick fences
- Ingest heading stack capped at depth 20
- All uncovered code paths tested: FTS5 error branch, `format_context` no-category, `strip_images`, `parse_markdown_sections`, web UI routes
- 56 tests pass (1 skipped — requires marker-pdf)
