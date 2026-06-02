from manuals_app.search import search_manuals, format_context, _sanitize_query


class TestSanitize:
    def test_basic_query(self):
        assert _sanitize_query("how to change oil") == "how to change oil"

    def test_internal_quotes_stripped(self):
        assert _sanitize_query('what "oil" means') == "what oil means"

    def test_no_special_chars(self):
        assert _sanitize_query("hello") == "hello"

    def test_strips_fts5_operators(self):
        assert _sanitize_query("oil*") == "oil"
        assert _sanitize_query("(oil)") == "oil"
        assert _sanitize_query("oil+filter") == "oilfilter"
        assert _sanitize_query("oil^filter") == "oilfilter"
        assert _sanitize_query("oil~filter") == "oilfilter"
        assert _sanitize_query("column:oil") == "columnoil"


class TestSearchManuals:
    def test_basic_search(self, populated_db):
        results = search_manuals(populated_db, "change oil")
        assert len(results) == 2

    def test_search_torque(self, populated_db):
        results = search_manuals(populated_db, "torque")
        assert len(results) == 1

    def test_search_single_result(self, populated_db):
        results = search_manuals(populated_db, "washer")
        assert len(results) == 1

    def test_empty_results(self, populated_db):
        results = search_manuals(populated_db, "xyznonexistent")
        assert results == []

    def test_category_filter(self, populated_db):
        results = search_manuals(populated_db, "oil", category="Automotive")
        assert all(r["category"] == "Automotive" for r in results)
        assert len(results) == 2

    def test_category_filter_nonexistent(self, populated_db):
        results = search_manuals(populated_db, "nope", category="Appliances")
        assert len(results) == 0

    def test_internal_quotes_safe(self, populated_db):
        results = search_manuals(populated_db, '"torque"')
        assert len(results) > 0

    def test_limit_param(self, populated_db):
        results = search_manuals(populated_db, "oil", limit=1)
        assert len(results) == 1

    def test_fts5_syntax_error_returns_empty(self, populated_db):
        results = search_manuals(populated_db, "-")
        assert results == []

    def test_empty_query_returns_empty(self, populated_db):
        results = search_manuals(populated_db, "")
        assert results == []

    def test_whitespace_query_returns_empty(self, populated_db):
        results = search_manuals(populated_db, "   ")
        assert results == []

    def test_result_keys(self, populated_db):
        results = search_manuals(populated_db, "oil")
        expected = {"filename", "category", "heading_path", "content_markdown", "rank"}
        for r in results:
            assert set(r.keys()) == expected


class TestFormatContext:
    def test_empty(self):
        assert format_context([]) == ""

    def test_single_result(self):
        results = [
            {"filename": "car.pdf", "category": "Automotive", "heading_path": "Engine > Oil Change", "content_markdown": "Use 5W-30 oil."}
        ]
        ctx = format_context(results)
        assert "[car.pdf (Automotive)]" in ctx
        assert "Engine > Oil Change" in ctx
        assert "5W-30" in ctx

    def test_multiple_results_separated(self):
        results = [
            {"filename": "car.pdf", "category": "Automotive", "heading_path": "Engine > Oil Change", "content_markdown": "Use 5W-30 oil."},
            {"filename": "car.pdf", "category": "Automotive", "heading_path": "Engine > Spark Plugs", "content_markdown": "Gap: 1.1mm."},
        ]
        ctx = format_context(results)
        assert "---" in ctx
        assert "Oil Change" in ctx
        assert "Spark Plugs" in ctx

    def test_no_category(self):
        results = [
            {"filename": "car.pdf", "category": "", "heading_path": "Engine", "content_markdown": "Content."},
            {"filename": "washer.pdf", "category": None, "heading_path": "Setup", "content_markdown": "Instructions."},
        ]
        ctx = format_context(results)
        assert ctx.count("[car.pdf]") == 1
        assert ctx.count("[washer.pdf]") == 1
        assert "(Automotive)" not in ctx
        assert "(Appliances)" not in ctx
