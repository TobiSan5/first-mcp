# tinydb_memorize — Detailed Guide

## Tags are how you find this later

The retrieval system scores memories by tag-embedding similarity. A memory is only findable
if it carries the right tags. Invest time in tag selection at storage time.

### Tag selection workflow
1. Extract 2–4 key concepts from the content: proper nouns, domain terms, project names.
2. Call `tinydb_find_similar_tags` for each concept to see if a near-synonym already exists.
3. Use existing tags over new ones wherever possible.
4. Add 1–2 *bridging tags*: broader context terms alongside specific project names.  
   Example: store `ergatax` + `timetabling` + `higher-education` rather than `ergatax` alone.
5. Smart tag mapping consolidates near-synonyms automatically at storage time.

### Good vs weak tags

| Good | Weak |
|---|---|
| `ergatax` (project name) | `software` |
| `higher-education` | `work` |
| `oslo` | `location` |
| `websockets` | `technology` |

## Categories

Use exactly one category per memory. Standard values: `user_context`, `preferences`,
`projects`, `learnings`, `corrections`, `facts`, `reminders`, `best_practices`.

## Importance

Set `importance=4` or `5` for memories that should always surface first in results.
Default is 3.
