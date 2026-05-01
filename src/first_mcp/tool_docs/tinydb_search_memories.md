# tinydb_search_memories — Detailed Guide

## Tag-first strategy

Tags are the primary search signal. The system scores every stored memory by how closely its
tags match the provided tags using embedding similarity — "scheduling" finds memories tagged
"timetabling", "ml" finds "machine-learning". Approximate tags work. Provide 2–4 tags.

If unsure what vocabulary exists, call `tinydb_find_similar_tags` first.

## Sorting

`sort_by` controls the order of memories that pass the tag filter:

| Value | Behaviour |
|---|---|
| `"relevance"` (default) | Highest relevance score first (see below) |
| `"date_desc"` | Most recently modified first |
| `"date_asc"` | Oldest first |

When tags are provided alongside a date sort, tag scoring still determines which memories
qualify; the survivors are then re-ordered by date.

### Relevance score

```
rank_score = Σ sim(query_tag, memory)²  +  0.333 × importance
```

- **sim(query_tag, memory)** — the maximum cosine similarity between the query tag's
  embedding and any of the memory's tag embeddings. Only query tags that score above an
  adaptive threshold (`mean + 0.5 × std` across all candidates) contribute.
- **Squaring** means strong matches (sim near 1.0) dominate; near-threshold hits count
  proportionally less.
- **0.333 × importance** adds ≈ 1.0 at the default importance level (3), up to 1.665 at
  level 5. This breaks ties between equally-relevant memories in favour of higher-importance
  ones, but cannot override a clear tag-relevance difference.

## Pagination

The first response contains `page_size` results (default 5). If `total_found > returned_count`:
1. Call `memory_next_page(next_page_token)` to get the next slice.
2. Repeat until `has_more` is `False` or you have enough context.
3. Stop early — there is no obligation to read all pages.

## `content_keywords`

A secondary filter applied to memory content text after tag scoring. Works as substring
matching — all provided words must appear in the content. It is not semantic.

Use it as a narrow disambiguator for known proper nouns or exact strings.

**Good:** `content_keywords="Harald Selvær"` — a known name that will match exactly.  
**Avoid:** `content_keywords="session summary April 28"` — too many words required to all match.

## Example calls

```
# Primary: tag-based
tinydb_search_memories(tags="ergatax,higher-education")

# Recent activity on a topic
tinydb_search_memories(tags="ergatax", sort_by="date_desc")

# Narrow down with a known keyword
tinydb_search_memories(tags="ergatax", content_keywords="Harald Selvær")
```
