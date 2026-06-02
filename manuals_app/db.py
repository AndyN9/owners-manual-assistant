import os
import sqlite3
from pathlib import Path


MAX_QUERY_LENGTH = 200
_BASE_DIR = Path(__file__).resolve().parent.parent


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    category TEXT
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    heading_path TEXT,
    content_markdown TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content_markdown,
    heading_path,
    content='document_chunks',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON document_chunks
BEGIN
    INSERT INTO chunks_fts(rowid, content_markdown, heading_path)
    VALUES (new.id, new.content_markdown, new.heading_path);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON document_chunks
BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content_markdown, heading_path)
    VALUES ('delete', old.id, old.content_markdown, old.heading_path);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON document_chunks
BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content_markdown, heading_path)
    VALUES ('delete', old.id, old.content_markdown, old.heading_path);
    INSERT INTO chunks_fts(rowid, content_markdown, heading_path)
    VALUES (new.id, new.content_markdown, new.heading_path);
END;
"""


def get_database_path() -> Path:
    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        return Path(env_path).resolve()
    return _BASE_DIR / "manuals_knowledge.db"


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: str | Path) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn
