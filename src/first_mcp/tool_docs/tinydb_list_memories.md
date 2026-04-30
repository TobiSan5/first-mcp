# tinydb_list_memories — Detailed Guide

## List vs Search: decision table

| Goal | Use |
|---|---|
| "What projects do I have stored?" | `tinydb_list_memories(category="projects")` |
| "What did I work on recently?" | `tinydb_list_memories(sort_by="date_desc")` |
| "What changed recently in my projects?" | `tinydb_list_memories(category="projects", sort_by="date_desc")` |
| "Find memories about machine learning" | `tinydb_search_memories(tags="machine-learning")` |

Use `tinydb_list_memories` for **inventory and browse** — when you want to see what exists
without a specific topic in mind. Use `tinydb_search_memories` when you have a topic.

## Sorting

| Value | Behaviour |
|---|---|
| `"relevance"` (default) | Highest importance first, then most recent |
| `"date_desc"` | Most recently modified first |
| `"date_asc"` | Oldest first |

## Pagination

First response returns `page_size` results (default 10). Call
`memory_next_page(next_page_token)` if `has_more` is True.
