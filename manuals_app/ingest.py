import argparse
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from manuals_app.db import get_database_path, init_db


EXTRACTORS = ("pypdf", "marker")


def strip_images(markdown: str) -> str:
    text = re.sub(r"!\[.*?\]\(.*?\)", "", markdown)
    text = re.sub(r"!\[.*?\]\[.*?\]", "", text)
    text = re.sub(
        r"\[.*?\]:\s*\S+\.(png|jpg|jpeg|gif|svg|webp|bmp)\s*",
        "",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    return text


MAX_HEADING_DEPTH = 20
CODE_FENCE_RE = re.compile(r"^(```+|~~~+)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def parse_markdown_sections(markdown: str) -> list[dict]:
    lines = markdown.split("\n")
    chunks = []
    heading_stack: list[tuple[int, str]] = []
    current_lines: list[str] = []
    in_code_block = False
    has_heading = False

    def flush_preamble():
        nonlocal current_lines
        if current_lines:
            content = strip_images("\n".join(current_lines)).strip()
            if content:
                chunks.append({"heading_path": "(preamble)", "content": content})
            current_lines = []

    def flush_current_section():
        nonlocal current_lines
        if current_lines:
            content = strip_images("\n".join(current_lines)).strip()
            if content:
                heading_path = " > ".join(t[1] for t in heading_stack)
                chunks.append({"heading_path": heading_path, "content": content})
            current_lines = []

    for line in lines:
        code_fence_match = CODE_FENCE_RE.match(line.strip())
        if code_fence_match:
            in_code_block = not in_code_block
            current_lines.append(line)
            continue

        if not in_code_block:
            m = HEADING_RE.match(line)
            if m:
                if not has_heading:
                    flush_preamble()
                else:
                    flush_current_section()

                level = len(m.group(1))
                heading_text = m.group(2).strip()

                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                if len(heading_stack) < MAX_HEADING_DEPTH:
                    heading_stack.append((level, heading_text))
                has_heading = True
                continue

        current_lines.append(line)

    if current_lines:
        if has_heading:
            content = strip_images("\n".join(current_lines)).strip()
            if content:
                heading_path = " > ".join(t[1] for t in heading_stack)
                chunks.append({"heading_path": heading_path + " > (postamble)", "content": content})
        else:
            flush_preamble()

    return chunks


TIMEOUT_SECONDS = 3600


def run_marker(pdf_path: Path, output_dir: Path) -> str:
    env = os.environ.copy()
    env["TORCH_DEVICE"] = "cpu"
    proc = subprocess.Popen(
        [
            "marker_single", str(pdf_path),
            "--output_dir", str(output_dir),
            "--DocumentProvider_pdftext_workers", "1",
            "--PdfProvider_pdftext_workers", "1",
            "--MarkdownRenderer_extract_images", "false",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    stderr_lines: list[str] = []

    def read_stderr():
        if proc.stderr:
            for line in proc.stderr:
                print(line, end="", flush=True)
                stderr_lines.append(line)

    reader = threading.Thread(target=read_stderr, daemon=True)
    reader.start()
    try:
        proc.wait(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise
    finally:
        reader.join(timeout=5)
    if proc.returncode != 0:
        error_text = "".join(stderr_lines)
        raise RuntimeError(
            f"Marker failed on {pdf_path}:\n{error_text}"
        )
    md_files = sorted(output_dir.rglob("*.md"))
    if not md_files:
        raise RuntimeError(
            f"Marker produced no markdown output for {pdf_path}"
        )
    return md_files[0].read_text(encoding="utf-8")


def run_pypdf(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def _truncate_pdf(pdf_path: Path, max_pages: int, output_dir: Path) -> Path:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)
    if total <= max_pages:
        return pdf_path
    writer = PdfWriter()
    for i in range(max_pages):
        writer.add_page(reader.pages[i])
    truncated = output_dir / f"{pdf_path.stem}_truncated.pdf"
    writer.write(str(truncated))
    print(f"  Truncated {total} pages → {max_pages} pages to save memory")
    return truncated.resolve()


def ingest_pdf(
    pdf_path: str | Path,
    category: str | None = None,
    db_path: str | Path | None = None,
    max_pages: int | None = None,
    extractor: str = "pypdf",
) -> int:
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if max_pages is not None and max_pages < 1:
        raise ValueError(f"max_pages must be >= 1, got {max_pages}")

    if db_path is None:
        db_path = get_database_path()

    print(f"Processing {pdf_path.name} with {extractor}...")
    with tempfile.TemporaryDirectory(prefix="manuals_ingest_") as tmpdir:
        tmp_path = Path(tmpdir)
        if max_pages is not None:
            pdf_path = _truncate_pdf(pdf_path, max_pages, tmp_path)
        output_dir = tmp_path

        if extractor == "marker":
            try:
                markdown = run_marker(pdf_path, output_dir)
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"Marker timed out on {pdf_path}")
            except FileNotFoundError as e:
                raise RuntimeError(
                    f"Marker not found. Install with: uv sync --group dev --extra ingest"
                ) from e
        else:
            markdown = run_pypdf(pdf_path)

        sections = parse_markdown_sections(markdown)
        if not sections:
            raise RuntimeError(f"No content sections found in {pdf_path}")

        conn = init_db(str(db_path))
        try:
            conn.execute(
                "INSERT INTO documents (filename, category) VALUES (?, ?)",
                (pdf_path.name, category),
            )
            doc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            chunk_data = [
                (doc_id, s["heading_path"], s["content"]) for s in sections
            ]
            conn.executemany(
                "INSERT INTO document_chunks (document_id, heading_path, content_markdown) VALUES (?, ?, ?)",
                chunk_data,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    return len(sections)


def main():
    parser = argparse.ArgumentParser(description="Ingest a PDF manual into the knowledge base")
    parser.add_argument("--file", required=True, help="Path to the PDF manual")
    parser.add_argument("--category", help="Manual category (e.g. Automotive, Appliances)")
    parser.add_argument("--max-pages", type=int, help="Limit to first N pages (saves RAM)")
    parser.add_argument("--extractor", choices=EXTRACTORS, default="pypdf",
                        help="Text extractor (default: pypdf, alternative: marker)")
    args = parser.parse_args()

    try:
        count = ingest_pdf(args.file, args.category, max_pages=args.max_pages, extractor=args.extractor)
        print(f"Done — ingested {count} sections into {get_database_path()}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
