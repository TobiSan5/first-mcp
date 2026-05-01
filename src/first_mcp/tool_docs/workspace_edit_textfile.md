# workspace_edit_textfile — Detailed Guide

## Workflow

1. Call `read_workspace_file` first to inspect the file and identify a suitable anchor string
   near the intended edit point.
2. Choose the appropriate mode.
3. For anchor-based modes, the anchor must be an exact substring of the file. Choose a unique
   string — if the anchor appears multiple times, `replace` changes only the first occurrence
   and `replace_all` changes all of them.

## Modes

| Mode | Anchor required | Behaviour |
|---|---|---|
| `append` | No | Add content at the end of the file |
| `prepend` | No | Add content at the beginning of the file |
| `insert_after` | Yes | Insert content immediately after the first occurrence of anchor |
| `insert_before` | Yes | Insert content immediately before the first occurrence of anchor |
| `replace` | Yes | Replace the first occurrence of anchor with content |
| `replace_all` | Yes | Replace all occurrences of anchor with content |

## Anchor tips

- Choose a long enough string to be unique in the file (a full sentence or distinctive phrase).
- For insertions, the anchor stays in the file — only new content is added around it.
- For replacements, the anchor itself is removed and replaced with content.
