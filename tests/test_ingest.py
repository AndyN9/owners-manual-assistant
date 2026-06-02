import os
import subprocess
import sys

import pytest

from manuals_app.db import init_db
from manuals_app.ingest import strip_images, parse_markdown_sections


def test_ingest_cli_no_args():
    result = subprocess.run(
        [sys.executable, "-m", "manuals_app.ingest"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_ingest_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "manuals_app.ingest", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--file" in result.stdout
    assert "--category" in result.stdout


def test_ingest_nonexistent_file():
    result = subprocess.run(
        [sys.executable, "-m", "manuals_app.ingest", "--file", "nonexistent.pdf"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


@pytest.mark.skipif(
    os.environ.get("SKIP_HEAVY") != "1",
    reason="Requires marker-pdf; set SKIP_HEAVY=1 to run",
)
def test_ingest_with_marker(db_path):
    """Integration test that requires marker-pdf installed."""
    from manuals_app.ingest import ingest_pdf

    os.environ["DATABASE_PATH"] = str(db_path)
    test_pdf = os.path.join(os.path.dirname(__file__), "fixtures", "sample.pdf")
    if not os.path.exists(test_pdf):
        pytest.skip("No fixture PDF available; run `make download-fixtures`")

    ingest_pdf(test_pdf, "Automotive")
    conn = init_db(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    assert count > 0
    chunk_count = conn.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0]
    assert chunk_count > 0
    conn.close()


class TestStripImages:
    def test_no_images(self):
        assert strip_images("plain text") == "plain text"

    def test_inline_image_removed(self):
        result = strip_images("text ![alt](img.png) more")
        assert result == "text  more"

    def test_ref_image_removed(self):
        result = strip_images("text ![alt][ref] more")
        assert result == "text  more"

    def test_ref_definition_removed(self):
        result = strip_images("[label]: https://example.com/photo.jpg")
        assert result == ""

    def test_non_image_ref_kept(self):
        result = strip_images("[label]: some text reference")
        assert result == "[label]: some text reference"

    def test_multiple_images(self):
        result = strip_images("a ![](a.png) b ![](b.jpg) c")
        assert result == "a  b  c"

    def test_image_extensions(self):
        for ext in ["png", "jpg", "jpeg", "gif", "svg", "webp", "bmp"]:
            result = strip_images(f"![x](img.{ext})")
            assert result == "", f"Failed for .{ext}"


class TestParseSections:
    def test_single_heading(self):
        md = "# Title\n\nContent here."
        sections = parse_markdown_sections(md)
        assert len(sections) == 1
        assert sections[0]["heading_path"] == "Title > (postamble)"
        assert sections[0]["content"] == "Content here."

    def test_preamble(self):
        md = "Some preamble text.\n\n# Real Title\nBody."
        sections = parse_markdown_sections(md)
        assert len(sections) == 2
        assert sections[0]["heading_path"] == "(preamble)"
        assert sections[0]["content"] == "Some preamble text."
        assert sections[1]["heading_path"] == "Real Title > (postamble)"
        assert sections[1]["content"] == "Body."

    def test_nested_headings(self):
        md = "# H1\nA\n## H2\nB\n### H3\nC"
        sections = parse_markdown_sections(md)
        assert len(sections) == 3
        assert sections[0]["heading_path"] == "H1"
        assert sections[0]["content"] == "A"
        assert sections[1]["heading_path"] == "H1 > H2"
        assert sections[1]["content"] == "B"
        assert sections[2]["heading_path"] == "H1 > H2 > H3 > (postamble)"
        assert sections[2]["content"] == "C"

    def test_heading_back_to_parent(self):
        md = "# H1\nA\n## H2\nB\n# Back to H1\nC"
        sections = parse_markdown_sections(md)
        assert len(sections) == 3
        assert sections[2]["heading_path"] == "Back to H1 > (postamble)"
        assert sections[2]["content"] == "C"

    def test_postamble(self):
        md = "# Title\nBody.\n\nTrailing text."
        sections = parse_markdown_sections(md)
        assert len(sections) == 1
        assert sections[0]["heading_path"] == "Title > (postamble)"
        assert sections[0]["content"] == "Body.\n\nTrailing text."

    def test_code_block_ignores_headings(self):
        md = "# Real\n```\n# Not a heading\n```\n## Also real"
        sections = parse_markdown_sections(md)
        assert len(sections) == 1
        assert sections[0]["heading_path"] == "Real"
        assert "# Not a heading" in sections[0]["content"]

    def test_tilde_fence_detected(self):
        md = "# Real\n~~~\n# Not a heading\n~~~\n## Also real"
        sections = parse_markdown_sections(md)
        assert len(sections) == 1
        assert sections[0]["heading_path"] == "Real"
        assert "# Not a heading" in sections[0]["content"]

    def test_images_stripped_from_content(self):
        md = "# Title\nHere is an image: ![diagram](pic.png)"
        sections = parse_markdown_sections(md)
        assert "pic.png" not in sections[0]["content"]

    def test_empty_markdown(self):
        assert parse_markdown_sections("") == []

    def test_no_headings(self):
        sections = parse_markdown_sections("Just a paragraph.\n\nAnother one.")
        assert len(sections) == 1
        assert sections[0]["heading_path"] == "(preamble)"
