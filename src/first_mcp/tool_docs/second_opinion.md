# second_opinion — Detailed Guide

## What it does

Sends a question to Gemini (`FIRST_MCP_ASSISTANT_MODEL`, default `gemini-2.5-flash`) and
returns the answer as plain text. Requires `GOOGLE_API_KEY`.

This is a different model talking, not a search or lookup. Treat the answer as one
perspective to weigh, not ground truth.

## When to use it

- **Trade-off analysis** — "What are the pros and cons of approach X vs Y?"
- **Wording / tone review** — "Does this message come across as intended?"
- **Sanity checks** — "Does this reasoning hold up?"
- **Cross-model comparison** — You already have Claude's take; this adds Gemini's.
- **Domain recall** — Quick factual questions where a second source is useful.

## When not to use it

- Real-time data (Gemini has a knowledge cutoff, same as Claude).
- Tasks that need tool access — Gemini here runs without tools.
- Anything sensitive that should not leave the local session.

## The `context` parameter

Pass background material that frames the question — a code snippet, a short summary,
or a list of constraints. Keep it focused; the model performs better with concise,
relevant context than a large dump.

**Good:**
```
context = "We are choosing a database for a read-heavy API with ~50 M rows."
question = "Would PostgreSQL or DynamoDB be a better fit, and why?"
```

**Avoid:**
```
context = "<entire codebase pasted here>"
question = "What should I change?"
```

## Example calls

```
# Simple question
second_opinion(question="Is there a meaningful difference between 'affect' and 'effect' in this sentence: 'The change will effect our timeline'?")

# With context
second_opinion(
    question="Which of these two approaches handles backpressure better?",
    context="Option A uses a bounded queue with a fixed thread pool. Option B uses reactive streams with demand signalling."
)
```
