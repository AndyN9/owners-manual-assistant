#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/../../../.." && pwd)"
MANUALS_DIR="$PROJECT_DIR/manuals"

cd "$PROJECT_DIR"

if [[ ! -d "$MANUALS_DIR" ]]; then
    echo "Error: manuals/ directory not found at $MANUALS_DIR" >&2
    exit 1
fi

mapfile -t PDFS < <(find "$MANUALS_DIR" -maxdepth 1 -name '*.pdf' -type f | sort)
TOTAL=${#PDFS[@]}

if [[ $TOTAL -eq 0 ]]; then
    echo "No PDFs found in manuals/" >&2
    echo '{"total":0,"new":0,"success":0,"failed":0,"results":[]}'
    exit 0
fi

echo "Found $TOTAL PDFs in manuals/" >&2

ALREADY=$(python3 -c "
from manuals_app.db import get_database_path, init_db
db = get_database_path()
conn = init_db(str(db))
rows = conn.execute('SELECT filename FROM documents').fetchall()
conn.close()
for r in rows:
    print(r['filename'])
" 2>/dev/null)

NEW_PDFS=()
for pdf in "${PDFS[@]}"; do
    name=$(basename "$pdf")
    if echo "$ALREADY" | grep -qxF "$name"; then
        echo "  Already indexed: $name" >&2
    else
        NEW_PDFS+=("$pdf")
    fi
done

NEW_COUNT=${#NEW_PDFS[@]}
echo "New: $NEW_COUNT" >&2

if [[ $NEW_COUNT -eq 0 ]]; then
    echo '{"total":0,"new":0,"success":0,"failed":0,"results":[]}'
    exit 0
fi

RESULTS=()
SUCCESS=0
FAILED=0
TOTAL_SECTIONS=0

for pdf in "${NEW_PDFS[@]}"; do
    name=$(basename "$pdf")
    echo "" >&2
    echo "Processing $name ..." >&2

    set +e
    OUTPUT=$(uv run python -m manuals_app.ingest --file "$pdf" 2>&1)
    EXIT_CODE=$?
    set -e

    if [[ $EXIT_CODE -eq 0 ]]; then
        SECTIONS=$(echo "$OUTPUT" | grep -oP '\d+(?= sections)' || echo "0")
        SUCCESS=$((SUCCESS + 1))
        TOTAL_SECTIONS=$((TOTAL_SECTIONS + SECTIONS))
        RESULTS+=("{\"file\":\"$name\",\"status\":\"ok\",\"sections\":$SECTIONS}")
        echo "  Done ($SECTIONS sections)" >&2
    else
        FAILED=$((FAILED + 1))
        ERROR=$(echo "$OUTPUT" | head -1)
        RESULTS+=("{\"file\":\"$name\",\"status\":\"failed\",\"error\":\"$ERROR\"}")
        echo "  Error: $ERROR" >&2
    fi
done

echo "" >&2
echo "Summary:" >&2
echo "  Total: $NEW_COUNT | Success: $SUCCESS | Failed: $FAILED" >&2
echo "  Sections added: $TOTAL_SECTIONS" >&2

JOINED=$(
    IFS=,
    echo "[${RESULTS[*]}]"
)

cat <<JSON
{
  "total": $NEW_COUNT,
  "success": $SUCCESS,
  "failed": $FAILED,
  "sections_added": $TOTAL_SECTIONS,
  "results": $JOINED
}
JSON
