import re
import sqlite3
from pathlib import Path

from manuals_app.db import get_connection

FTS5_SPECIAL = re.compile(r'["*+()^~:]')


SEARCH_SQL = """
SELECT doc.filename, doc.category, chunk.heading_path, chunk.content_markdown,
       rank
FROM chunks_fts
JOIN document_chunks chunk ON chunks_fts.rowid = chunk.id
JOIN documents doc ON chunk.document_id = doc.id
WHERE chunks_fts MATCH ?
  AND (? IS NULL OR doc.category = ?)
ORDER BY rank
LIMIT ?
"""


def _sanitize_query(query: str) -> str:
    return FTS5_SPECIAL.sub("", query)


def search_manuals(
    db_path: str | Path,
    query: str,
    category: str | None = None,
    limit: int = 5,
) -> list[dict]:
    conn = get_connection(db_path)
    try:
        fts_query = _sanitize_query(query)
        rows = conn.execute(
            SEARCH_SQL,
            (fts_query, category, category, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def format_context(results: list[dict]) -> str:
    if not results:
        return ""

    parts = []
    for r in results:
        if r["category"]:
            header = f"[{r['filename']} ({r['category']})] {r['heading_path']}"
        else:
            header = f"[{r['filename']}] {r['heading_path']}"
        parts.append(f"{header}\n{r['content_markdown']}")

    return "\n\n---\n\n".join(parts)
