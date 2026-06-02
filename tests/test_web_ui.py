import tempfile

import pytest
from fastapi.testclient import TestClient

from manuals_app.db import init_db
from manuals_app.web_ui import app


@pytest.fixture
def client(monkeypatch):
    db = tempfile.mktemp(suffix=".db")
    conn = init_db(db)
    conn.execute("INSERT INTO documents (filename, category) VALUES (?,?)", ("car.pdf", "Automotive"))
    doc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO document_chunks (document_id, heading_path, content_markdown) VALUES (?,?,?)",
        (doc_id, "Engine > Oil Change", "Use 5W-30 oil. Drain plug: 30 Nm."),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("DATABASE_PATH", db)
    with TestClient(app) as c:
        yield c
    import os
    os.unlink(db)


class TestSearchForm:
    def test_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_contains_form(self, client):
        r = client.get("/")
        assert "Manuals Search" in r.text


class TestSearchResults:
    def test_basic_search(self, client):
        r = client.get("/search", params={"q": "oil"})
        assert r.status_code == 200
        assert "5W-30" in r.text

    def test_no_results(self, client):
        r = client.get("/search", params={"q": "xyznonexistent"})
        assert r.status_code == 200
        assert "No matching content" in r.text

    def test_blank_query_rejected(self, client):
        r = client.get("/search", params={"q": ""})
        assert r.status_code == 422

    def test_whitespace_query_rejected(self, client):
        r = client.get("/search", params={"q": "   "})
        assert r.status_code == 400

    def test_limit_out_of_range(self, client):
        r = client.get("/search", params={"q": "oil", "limit": 100})
        assert r.status_code == 422

    def test_limit_negative(self, client):
        r = client.get("/search", params={"q": "oil", "limit": 0})
        assert r.status_code == 422

    def test_oversized_query_rejected(self, client):
        r = client.get("/search", params={"q": "a" * 300})
        assert r.status_code == 422

    def test_results_grouped_by_filename(self, client):
        r = client.get("/search", params={"q": "oil"})
        assert "car.pdf" in r.text

    def test_query_displayed(self, client):
        r = client.get("/search", params={"q": "oil"})
        assert "oil" in r.text

    def test_category_filter(self, client):
        r = client.get("/search", params={"q": "oil", "category": "Automotive"})
        assert r.status_code == 200
        assert "5W-30" in r.text
