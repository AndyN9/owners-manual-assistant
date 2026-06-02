# Improve Web UI

## Issues

### 1. Category dropdown is hardcoded
`templates/search.html:26-30` has a static `<select>` with only "Automotive" and "Appliances". Should be populated dynamically from `SELECT DISTINCT category FROM documents WHERE category IS NOT NULL`.

### 2. Results page is raw
`templates/results.html:34` dumps `chunk.content_markdown` inside `<pre>` — no query term highlighting, no snippets, full raw text. For long chunks this is unreadable.

### 3. No document listing
No page to see all ingested documents. Users have to guess filenames. Add a `/documents` route listing everything in the DB.

### 4. No pagination
`/search` accepts `limit` (1–50) but there's no offset/pagination when a query returns many results.

### 5. Bland visual design
Minimal CSS, no branding, no favicon, no dark mode, no responsive layout for mobile.

### 6. Missing primary key on results
No way to link to a specific chunk. Each chunk should have a stable URL like `/chunk/{id}`.

## Suggested Work

- [ ] Add a `/categories` endpoint or inline query for dynamic category dropdown
- [ ] Highlight matching terms in results (split on query words, wrap matches in `<mark>`)
- [ ] Add `/documents` page with list of all ingested files and chunk counts
- [ ] Add `/chunk/{id}` route for individual chunk view with permanent link
- [ ] Add offset-based pagination to `/search`
- [ ] Improve CSS (dark mode, responsive, better typography)
- [ ] Show search snippet instead of full content, with expand-to-full option
