# Memory System — Workflow Guide

## Retrieval

Tags are the primary retrieval mechanism — not free-text content search. The search engine
scores memories by tag-embedding similarity, so "scheduling" will surface a memory tagged
"timetabling" even if the word never appears in the content.

### Recommended retrieval steps
1. If unsure what tags exist, call `tinydb_find_similar_tags` or `tinydb_get_all_tags`.
2. Call `tinydb_search_memories` with 2–4 relevant tags and the default `page_size`.
3. If `total_found > returned_count`, call `memory_next_page` to expand context one page at a
   time — stop when you have enough, not necessarily at the last page.
4. Use `tinydb_list_memories` to browse a category without a topic filter, or when you have no
   specific tags. Use `sort_by="date_desc"` to see what changed recently.

### Search strategies

| Goal | Tool call |
|---|---|
| Find by topic | `tinydb_search_memories(tags="ergatax,higher-education")` |
| Recent activity | `tinydb_list_memories(sort_by="date_desc")` |
| Category inventory | `tinydb_list_memories(category="projects")` |
| Recent activity in category | `tinydb_list_memories(category="projects", sort_by="date_desc")` |
| Keyword in content | `tinydb_search_memories(content_keywords="Harald Selvær")` |

## Storage

Tags chosen at storage time determine how easily a memory can be found later.

### Tag selection workflow
1. Extract 2–4 key concepts from the content: proper nouns, domain terms, project names.
2. For each concept, call `tinydb_find_similar_tags` to see if a close tag already exists.
3. Prefer existing tags over new ones — avoids vocabulary fragmentation.
4. Add 1–2 *bridging tags* for broader context alongside specific project names (e.g. alongside
   `ergatax` also add `timetabling` and `higher-education`).
5. Avoid generic tags: "info", "note", "software", "work".

### Categories
Use one per memory: `user_context`, `preferences`, `projects`, `learnings`, `corrections`,
`facts`, `reminders`, `best_practices`.

### Importance scale

| Value | Meaning |
|---|---|
| 5 | Critical — must always surface |
| 4 | High — frequently referenced |
| 3 | Normal (default) |
| 2 | Low — useful but not critical |
| 1 | Reference — rarely accessed |

## Session start

Call `tinydb_search_memories(tags="session-start")` to load stored preferences and workflows.
Paginate at least 2–3 pages before concluding — important memories may not be on the first page.

## Troubleshooting

**Memory not found in search:**
- Verify it exists: `tinydb_recall_memory(memory_id)`
- Try broader tags: `tinydb_find_similar_tags("concept")`
- Browse the expected category: `tinydb_list_memories(category="projects")`

**Tag proliferation:**
- Always call `tinydb_find_similar_tags` before coining a new tag.
- To consolidate: use `tinydb_get_all_tags()` to spot near-duplicates, then
  `tinydb_update_memory()` to re-tag affected memories.
