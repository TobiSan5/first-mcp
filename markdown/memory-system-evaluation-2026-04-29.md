# Memory System Evaluation — first-mcp TinyDB
*Diagnostic session: April 29, 2026*

---

## 1. Background

This report summarises findings from a hands-on diagnostic session in which the
`first-mcp-installed` TinyDB memory server was tested systematically. The trigger
was a session-start retrieval failure: several relevant memories — including the
full Ergatax project context — were not surfaced despite multiple search attempts
with semantically appropriate terms.

---

## 2. Strengths

### 2.1 Tag-based semantic search works well when tags are correct
When the exact tag (or a semantically close one) is used, retrieval is fast and
accurate. Searching `fagskole-oslo` reliably returned the ATA negotiation notes;
searching `ergatax` returned all six Ergatax memories with no false positives.

### 2.2 `tinydb_find_similar_tags` is a useful pre-search tool
The tool correctly identified related tags (`fagskole → fagskole-oslo`,
`bygg → byggfag`, etc.) before search calls, allowing vocabulary gaps to be
bridged. This tool should be part of every session-start workflow when the topic
is uncertain.

### 2.3 `tinydb_list_memories` with `sort_by=date_desc` is a reliable fallback
When tag-based search failed to surface a memory, browsing all memories sorted by
recency reliably found recent entries. This is the correct fallback strategy when
topic tags are unknown or sparse.

### 2.4 `query` parameter can match content keywords
When a sufficiently specific and exact term is used (e.g. `"Harald Selvær"`), the
`query` parameter successfully retrieves memories containing that string. Useful
as a last-resort precision tool for known proper nouns.

---

## 3. Weaknesses

### 3.1 `query` parameter does NOT perform semantic search
Despite the parameter being available alongside `semantic_search=true`, the
`query` field appears to perform keyword/substring matching on memory content —
not embedding-based semantic retrieval. Concrete evidence:

- `query="Allan Bjorn-Tore timeplan"` → 0 results
- `query="Harald Selvær"` → 5 results (correct)

This means `query` is only reliable for exact or near-exact string matches,
not for conceptual retrieval. The parameter name and placement are misleading
given that tags use semantic similarity.

### 3.2 Combining `query` + `category` breaks retrieval
`query="session summary April 28"` with `category="projects"` returned 0 results,
even though memories matching both constraints exist. The interaction between
`query` and `category` filtering appears to be broken or overly restrictive.
Workaround: never combine `query` with `category`.

### 3.3 Tag proliferation makes retrieval brittle
The memory store has accumulated 100+ distinct categories and an unknown number
of tags. Many memories are tagged too narrowly (e.g. only `ergatax`) without
broader contextual tags (e.g. `timetabling`, `higher-education`, `scheduling`).
A memory is only as findable as its weakest tag.

**Root cause:** No systematic tag review at storage time. Tags are coined
per-session without checking for existing synonyms or adding bridging tags.

### 3.4 `memory_next_page` pagination is unreliable
In one test, repeated calls to `memory_next_page` returned the same
`next_page_token` as the previous call, producing an infinite loop with no new
results. This was observed when paginating a `session-start` tag search
(total_found: 50, page_size: 10). The underlying paging mechanism may have a
bug when a semantic-search result set is exhausted or cached improperly.

### 3.5 Session-start search only reads first page
The session-start initialisation routine searched for `session-start` tagged
memories but only consumed the first page (5 results out of 26 total). Several
highly relevant memories — including the projects-overview memory and the
IT-HMS project — were on later pages and were therefore invisible at session
start. Workflow documentation says to paginate, but this was not consistently
followed.

### 3.6 `query` + `sort_by=date_desc` combination returns 0 results
`query="session summary April 28"` with `sort_by="date_desc"` returned 0 results
via `tinydb_search_memories`, even without a category filter. The `query`
parameter appears incompatible with date-sorted retrieval modes in the current
implementation.

---

## 4. Recommendations

### For storage discipline
- Always call `tinydb_find_similar_tags` before storing a new memory.
- Add 2–3 *bridging tags* in addition to the specific project name: e.g.
  alongside `ergatax` always add `timetabling`, `higher-education`.
- Avoid coining new tags when a near-synonym already exists.

### For retrieval strategy
- **Primary:** Tag-based search with 2–4 well-chosen tags.
- **Fallback 1:** `tinydb_list_memories` with `sort_by=date_desc` to browse recent
  memories when tags are uncertain.
- **Fallback 2:** `query` with a specific proper noun (name, project name) as a
  last-resort substring match.
- **Avoid:** Combining `query` with `category`; combining `query` with
  `sort_by=date_desc`.

### For session-start
- After the initial `session-start` search, always paginate at least 2–3 pages
  before concluding retrieval.
- Or: increase `page_size` to 15–20 on the session-start call to capture more
  of the total_found set in one round trip.

### For the server implementation (potential bugs to investigate)
1. `memory_next_page` returning the same token repeatedly — likely a caching or
   exhaustion bug in the paginator.
2. `query` + `category` combination returning 0 results — filter interaction bug.
3. `query` not performing semantic search despite `semantic_search=true` — the
   parameter may only apply to tag scoring, not content search.

---

## 5. Summary table

| Feature | Status | Notes |
|---|---|---|
| Tag search (semantic) | ✅ Works well | Primary retrieval mechanism |
| `find_similar_tags` | ✅ Works well | Use before every search |
| `list_memories` (date_desc) | ✅ Works well | Best fallback |
| `query` (exact match) | ⚠️ Partial | Only substring, not semantic |
| `query` + `category` | ❌ Broken | Returns 0 results |
| `query` + `date_desc` | ❌ Broken | Returns 0 results |
| Pagination | ⚠️ Unstable | Same token returned on exhaustion |
| Tag discipline at storage | ⚠️ Inconsistent | Root cause of most retrieval failures |

---

*Report generated by Claude (Sonnet 4.6) based on live diagnostic testing.*
