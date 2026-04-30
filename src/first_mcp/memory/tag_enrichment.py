"""
Agentic background tag enrichment.

Runs as a long-lived asyncio.Task started from the FastMCP lifespan context manager.
Each cycle fetches a batch of un-enriched memories, calls Gemini once with a
structured-output schema, applies the resulting tag patches (with a hard similarity
guardrail on replacements), and records each memory in the enrichment register.

Integration point (server_impl.py):

    @asynccontextmanager
    async def _lifespan(server: FastMCP):
        task = asyncio.create_task(tag_enrichment_loop())
        try:
            yield {}
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    mcp = FastMCP(name="First MCP Server", lifespan=_lifespan)
"""

import asyncio
import contextlib
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from tinydb import Query

try:
    import google.genai as genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from .database import get_memory_tinydb, get_tags_tinydb, get_enrichment_tinydb
from .tag_tools import tinydb_find_similar_tags, increment_tag_usage, decrement_tag_usage
from ..embeddings import cosine_similarity as _cosine_similarity, EMBEDDING_MODEL


ENRICHMENT_LLM_MODEL = "gemini-2.5-flash"
REPLACEMENT_SIMILARITY_THRESHOLD = 0.85
DEFAULT_BATCH_SIZE = 10


# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

class TagReplacement(BaseModel):
    old_tag: str
    new_tag: str  # must be an existing tag in the registry


class MemoryTagPatch(BaseModel):
    memory_id: str
    replacements: List[TagReplacement]  # swap old → existing canonical tag
    add_existing: List[str]             # existing registry tags to add
    add_new: List[str]                  # new bridging tags (need embedding registration)
    drop: List[str]                     # tags to remove


class BatchResponse(BaseModel):
    patches: List[MemoryTagPatch]


# ---------------------------------------------------------------------------
# Enrichment register helpers
# ---------------------------------------------------------------------------

def mark_enriched(memory_id: str, tags_added: List[str]) -> None:
    """Record that a memory has been reviewed by the enrichment agent."""
    db = get_enrichment_tinydb()
    table = db.table('enriched')
    table.insert({
        'memory_id': memory_id,
        'enriched_at': datetime.now().isoformat(),
        'tags_added': tags_added,
    })
    db.close()


def remove_from_enrichment_register(memory_id: str) -> None:
    """Remove a memory from the register so it re-enters the enrichment queue.

    Call this whenever a memory's tags are changed or the memory is deleted.
    """
    db = get_enrichment_tinydb()
    table = db.table('enriched')
    Record = Query()
    table.remove(Record.memory_id == memory_id)
    db.close()


def get_unenriched_memory_ids(limit: int) -> List[str]:
    """Return IDs of memories not yet in the enrichment register, up to `limit`."""
    memory_db = get_memory_tinydb()
    memories_table = memory_db.table('memories')
    all_memories = memories_table.all()
    memory_db.close()

    enrich_db = get_enrichment_tinydb()
    enrich_table = enrich_db.table('enriched')
    enriched_ids = {r['memory_id'] for r in enrich_table.all()}
    enrich_db.close()

    return [m['id'] for m in all_memories if m.get('id') not in enriched_ids][:limit]


# ---------------------------------------------------------------------------
# Tag registry helpers
# ---------------------------------------------------------------------------

def _get_tag_meta(tag_name: str) -> Optional[Dict[str, Any]]:
    """Return the full tag record for `tag_name`, or None if not found."""
    tags_db = get_tags_tinydb()
    tags_table = tags_db.table('tags')
    Record = Query()
    results = tags_table.search(Record.tag == tag_name)
    tags_db.close()
    return results[0] if results else None


async def _register_new_tags_async(client: "genai.Client", new_tags: List[str]) -> None:
    """Register brand-new tags with embeddings generated concurrently.

    Tags that already exist in the registry are skipped (their usage count
    will be bumped by _bump_tag_usage if needed).
    """
    if not new_tags:
        return

    tags_db = get_tags_tinydb()
    tags_table = tags_db.table('tags')
    Record = Query()

    truly_new = [t for t in new_tags if not tags_table.search(Record.tag == t)]
    tags_db.close()

    if not truly_new:
        return

    # Concurrent embedding generation
    responses = await asyncio.gather(
        *[
            client.aio.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=tag,
            )
            for tag in truly_new
        ],
        return_exceptions=True,
    )

    now = datetime.now().isoformat()
    tags_db = get_tags_tinydb()
    tags_table = tags_db.table('tags')

    for tag, resp in zip(truly_new, responses):
        if isinstance(resp, Exception):
            embedding: List[float] = []
            extra: Dict[str, Any] = {}
        else:
            embedding = list(resp.embeddings[0].values)
            extra = {
                'embedding_generated_at': now,
                'embedding_model': EMBEDDING_MODEL,
            }

        tags_table.insert({
            'tag': tag,
            'usage_count': 1,
            'created_at': now,
            'last_used_at': now,
            'embedding': embedding,
            **extra,
        })

    tags_db.close()


# ---------------------------------------------------------------------------
# Guardrail
# ---------------------------------------------------------------------------

def _replacement_passes_guardrail(old_tag: str, new_tag: str) -> bool:
    """Accept a replacement only when similarity > threshold AND new tag is more used."""
    old_meta = _get_tag_meta(old_tag)
    new_meta = _get_tag_meta(new_tag)
    if not old_meta or not new_meta:
        return False

    old_emb = old_meta.get('embedding', [])
    new_emb = new_meta.get('embedding', [])
    if not old_emb or not new_emb:
        return False

    if _cosine_similarity(old_emb, new_emb) < REPLACEMENT_SIMILARITY_THRESHOLD:
        return False

    return new_meta.get('usage_count', 0) > old_meta.get('usage_count', 0)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(memories: List[Dict[str, Any]], similar_map: Dict[str, List[Dict]]) -> str:
    lines = [
        "You are a memory tag quality agent. Review each memory and suggest minimal tag improvements.",
        "",
        "Rules:",
        "- REPLACE: swap a tag for a semantically equivalent canonical tag already in the registry.",
        "  Never replace proper nouns, project names, or abbreviations with generic terms.",
        "- ADD EXISTING: add a registry tag that is clearly relevant but missing.",
        "- ADD NEW: add a short bridging/broader concept tag that does not yet exist.",
        "  Only suggest this when the memory is clearly missing a useful general category.",
        "- DROP: remove a tag that is misleading or fully superseded by a replacement.",
        "",
        "Be conservative. Leave all lists empty if no improvement is obvious.",
        "Each memory_id in your response must match exactly.",
        "",
        "--- MEMORIES ---",
    ]

    for mem in memories:
        mid = mem.get('id', '')
        preview = (mem.get('content') or '')[:250].replace('\n', ' ')
        current_tags = mem.get('tags', [])

        lines.append(f"\nmemory_id: {mid}")
        lines.append(f"content: {preview}")
        lines.append(f"current_tags: {current_tags}")

        for tag in current_tags:
            candidates = similar_map.get(tag, [])
            shown = [c for c in candidates if c.get('tag') != tag][:5]
            if shown:
                cand_str = ', '.join(
                    f"{c['tag']}(sim={c['similarity']:.2f}, used={c['usage_count']}x)"
                    for c in shown
                )
                lines.append(f"  similar_to '{tag}': [{cand_str}]")

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Core batch enrichment
# ---------------------------------------------------------------------------

async def enrich_batch(memory_ids: List[str]) -> Dict[str, Any]:
    """
    Enrich tags for a batch of memories with a single Gemini LLM call.

    Returns a summary dict with counts of actions taken.
    """
    if not GENAI_AVAILABLE:
        return {'success': False, 'error': 'google-genai not installed'}

    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return {'success': False, 'error': 'GOOGLE_API_KEY not set'}

    # Load memories
    memory_db = get_memory_tinydb()
    memories_table = memory_db.table('memories')
    Record = Query()
    memories = [
        rows[0]
        for mid in memory_ids
        for rows in [memories_table.search(Record.id == mid)]
        if rows
    ]
    memory_db.close()

    if not memories:
        return {'success': True, 'processed': 0}

    # Pre-fetch similar tags for every tag in this batch (synchronous; fast in-process)
    all_tags = {tag for m in memories for tag in m.get('tags', [])}
    similar_map: Dict[str, List[Dict]] = {}
    for tag in all_tags:
        result = tinydb_find_similar_tags(tag, limit=6, min_similarity=0.55)
        similar_map[tag] = result.get('similar_tags', []) if result.get('success') else []

    prompt = _build_prompt(memories, similar_map)

    # Single async Gemini call with structured output
    client = genai.Client(api_key=api_key)
    response = await client.aio.models.generate_content(
        model=ENRICHMENT_LLM_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BatchResponse,
        ),
    )

    batch_result = BatchResponse.model_validate_json(response.text)

    # Apply patches
    total_replaced = 0
    total_added = 0
    total_dropped = 0

    memory_db = get_memory_tinydb()
    memories_table = memory_db.table('memories')

    for patch in batch_result.patches:
        mid = patch.memory_id
        rows = memories_table.search(Record.id == mid)
        if not rows:
            continue

        mem = rows[0]
        tags: List[str] = list(mem.get('tags', []))
        original_tags = list(tags)
        tags_added: List[str] = []

        # Replacements — hard guardrail enforced independently of LLM judgment
        replaced_out: List[str] = []
        for repl in patch.replacements:
            if repl.old_tag in tags and _replacement_passes_guardrail(repl.old_tag, repl.new_tag):
                tags.remove(repl.old_tag)
                replaced_out.append(repl.old_tag)
                if repl.new_tag not in tags:
                    tags.append(repl.new_tag)
                    increment_tag_usage([repl.new_tag])
                total_replaced += 1
        decrement_tag_usage(replaced_out)

        # Add existing registry tags; bump their usage count
        to_add_existing = [t for t in patch.add_existing if t not in tags]
        if to_add_existing:
            increment_tag_usage(to_add_existing)
            tags.extend(to_add_existing)
            tags_added.extend(to_add_existing)
            total_added += len(to_add_existing)

        # Register truly-new tags with async concurrent embedding, then add
        if patch.add_new:
            await _register_new_tags_async(client, patch.add_new)
            for tag in patch.add_new:
                if tag not in tags:
                    tags.append(tag)
                    tags_added.append(tag)
                    total_added += 1

        # Drop tags and decrement their usage counts
        dropped: List[str] = []
        for tag in patch.drop:
            if tag in tags:
                tags.remove(tag)
                dropped.append(tag)
                total_dropped += 1
        decrement_tag_usage(dropped)

        # Write back only if something changed
        if tags != original_tags:
            memories_table.update(
                {'tags': tags, 'last_modified': datetime.now().isoformat()},
                Record.id == mid,
            )

        mark_enriched(mid, tags_added)

    memory_db.close()

    return {
        'success': True,
        'processed': len(memories),
        'replaced': total_replaced,
        'added': total_added,
        'dropped': total_dropped,
    }


# ---------------------------------------------------------------------------
# Background loop
# ---------------------------------------------------------------------------

async def tag_enrichment_loop(
    interval_short: int = 60,
    interval_long: int = 1200,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> None:
    """
    Infinite background loop enriching un-reviewed memory tags.

    Short sleep (~60 s) while unenriched memories exist; long sleep (~20 min) when
    all are covered. Start this as an asyncio.Task from the FastMCP lifespan.
    """
    print("Tag enrichment agent started.", file=sys.stderr)

    while True:
        try:
            candidates = get_unenriched_memory_ids(batch_size)

            if candidates:
                print(
                    f"[tag_enrichment] Processing {len(candidates)} memories...",
                    file=sys.stderr,
                )
                result = await enrich_batch(candidates)
                print(f"[tag_enrichment] {result}", file=sys.stderr)
                await asyncio.sleep(interval_short)
            else:
                await asyncio.sleep(interval_long)

        except asyncio.CancelledError:
            print("Tag enrichment agent stopped.", file=sys.stderr)
            raise
        except Exception as exc:
            print(f"[tag_enrichment] Error: {exc}", file=sys.stderr)
            await asyncio.sleep(interval_short)
