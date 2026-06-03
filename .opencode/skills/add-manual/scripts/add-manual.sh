#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/../../../.." && pwd)"

usage() {
    cat >&2 <<EOF
Usage: $(basename "$0") --file <pdf-path> [--category <cat>] [--extractor pypdf|marker] [--max-pages <N>]

Ingest a single PDF manual into the knowledge base.
EOF
    exit 1
}

FILE=""
CATEGORY=""
EXTRACTOR="pypdf"
MAX_PAGES=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --file) FILE="$2"; shift 2 ;;
        --category) CATEGORY="$2"; shift 2 ;;
        --extractor) EXTRACTOR="$2"; shift 2 ;;
        --max-pages) MAX_PAGES="$2"; shift 2 ;;
        *) usage ;;
    esac
done

if [[ -z "$FILE" ]]; then
    echo "Error: --file is required" >&2
    exit 1
fi

if [[ ! -f "$FILE" ]]; then
    echo "Error: PDF not found: $FILE" >&2
    exit 1
fi

cd "$PROJECT_DIR"

ARGS=("--file" "$FILE" "--extractor" "$EXTRACTOR")
if [[ -n "$CATEGORY" ]]; then
    ARGS+=("--category" "$CATEGORY")
fi
if [[ -n "$MAX_PAGES" ]]; then
    ARGS+=("--max-pages" "$MAX_PAGES")
fi

echo "Ingesting $FILE with $EXTRACTOR..." >&2
OUTPUT=$(uv run python -m manuals_app.ingest "${ARGS[@]}" 2>&1)
echo "$OUTPUT" >&2

SECTION_COUNT=$(echo "$OUTPUT" | grep -oP '\d+(?= sections)' || echo "")

BASENAME=$(basename "$FILE" .pdf)
echo "Verifying search for '$BASENAME'..." >&2
VERIFY=$(python3 -c "
from manuals_app.search import search_manuals
from manuals_app.db import get_database_path
results = search_manuals(get_database_path(), '$BASENAME', limit=5)
print(len(results))
" 2>&1) || VERIFY="?"

cat <<JSON
{
  "file": "$FILE",
  "category": "${CATEGORY:-null}",
  "extractor": "$EXTRACTOR",
  "sections": ${SECTION_COUNT:-0},
  "verify_results": ${VERIFY:-0},
  "status": "ok"
}
JSON
