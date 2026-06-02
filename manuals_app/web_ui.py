import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from manuals_app.db import MAX_QUERY_LENGTH, get_database_path
from manuals_app.search import search_manuals

logger = logging.getLogger(__name__)

app = FastAPI(title="Manuals Search")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/", response_class=HTMLResponse)
async def search_form(request: Request):
    return templates.TemplateResponse(
        request, "search.html",
    )


@app.get("/search", response_class=HTMLResponse)
async def search_results(
    request: Request,
    q: str = Query("", min_length=1, max_length=MAX_QUERY_LENGTH),
    category: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query must not be blank")
    try:
        db_path = get_database_path()
        results = await asyncio.to_thread(
            search_manuals, db_path, q, category=category, limit=limit,
        )
    except Exception:
        logger.exception("Search failed")
        raise HTTPException(status_code=500, detail="Search failed due to an internal error.")

    grouped: dict[str, list] = {}
    for r in results:
        filename = r["filename"]
        if filename not in grouped:
            grouped[filename] = []
        grouped[filename].append(r)

    return templates.TemplateResponse(
        request, "results.html",
        {
            "query": q,
            "category": category,
            "grouped": grouped,
            "total": len(results),
        },
    )


def main():
    uvicorn.run(app, host="127.0.0.1", port=8080)


if __name__ == "__main__":
    main()
