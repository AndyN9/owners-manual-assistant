from manuals_app.db import init_db, get_database_path


def test_init_db_creates_tables(db_path):
    conn = init_db(db_path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {r[0] for r in tables}
    assert "documents" in table_names
    assert "document_chunks" in table_names
    assert "chunks_fts" in table_names
    conn.close()


def test_init_db_wal_mode(db_path):
    conn = init_db(db_path)
    journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal == "wal"
    conn.close()


def test_init_db_fts_triggers(db_path):
    conn = init_db(db_path)
    triggers = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger'"
    ).fetchall()
    trigger_names = {r[0] for r in triggers}
    assert "chunks_ai" in trigger_names
    assert "chunks_ad" in trigger_names
    assert "chunks_au" in trigger_names
    conn.close()


def test_document_insert(db_path):
    conn = init_db(db_path)
    conn.execute("INSERT INTO documents (filename, category) VALUES (?, ?)", ("test.pdf", "Test"))
    conn.commit()
    row = conn.execute("SELECT filename, category FROM documents").fetchone()
    assert row["filename"] == "test.pdf"
    assert row["category"] == "Test"
    conn.close()


def test_chunk_insert_and_fts_sync(db_path):
    conn = init_db(db_path)
    conn.execute("INSERT INTO documents (filename, category) VALUES (?, ?)", ("doc.pdf", "Book"))
    doc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO document_chunks (document_id, heading_path, content_markdown) VALUES (?, ?, ?)",
        (doc_id, "Chapter 1", "Hello world content here"),
    )
    conn.commit()
    row = conn.execute("SELECT count(*) as cnt FROM chunks_fts").fetchone()
    assert row["cnt"] > 0
    conn.close()


def test_get_database_path_default():
    path = get_database_path()
    assert path is not None
    assert str(path).endswith(".db")
