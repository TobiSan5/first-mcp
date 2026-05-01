"""
Agentic background tag enrichment.

Runs as a long-lived asyncio.Task started from the FastMCP lifespan context manager.
Each cycle fetches un-enriched memories and calls Gemini once per memory with a
structured-output schema, applies the resulting tag patch (with a hard similarity
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
import pathlib
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / 'prompts'

from pydantic import BaseModel
from tinydb import Query

from .database import get_memory_tinydb, get_tags_tinydb, get_enrichment_tinydb
from .tag_tools import increment_tag_usage, decrement_tag_usage
from ..embeddings import cosine_similarity as _cosine_similarity, EMBEDDING_MODEL


ENRICHMENT_LLM_MODEL = os.getenv('FIRST_MCP_ENRICHMENT_MODEL', 'gemini-2.5-flash')
MAX_TAGS_PER_MEMORY = int(os.getenv('FIRST_MCP_MAX_TAGS', '4'))
MIN_TAGS_PER_MEMORY = int(os.getenv('FIRST_MCP_MIN_TAGS', '2'))
REPLACEMENT_SIMILARITY_THRESHOLD = 0.85


def _log(msg: str) -> None:
    entry = f"{datetime.now().isoformat()} {msg}\n"
    data_path = os.getenv('FIRST_MCP_DATA_PATH', '')
    if data_path:
        try:
            log_path = pathlib.Path(data_path) / 'enrichment.log'
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(entry)
        except OSError:
            pass
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

class TagReplacement(BaseModel):
    old_tag: str
    new_tag: str  # must be an existing tag in the registry


class MemoryTagPatch(BaseModel):
    replacements: List[TagReplacement]  # swap old → existing canonical tag
    add_existing: List[str]             # existing registry tags to add
    add_new: List[str]                  # new bridging tags (need embedding registration)
    drop: List[str]                     # tags to remove


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

def _build_prompt(mem: Dict[str, Any], similar_map: Dict[str, List[Dict]]) -> str:
    template = (_PROMPTS_DIR / 'tag_enrichment.md').read_text(encoding='utf-8')
    header = template.format(min_tags=MIN_TAGS_PER_MEMORY, max_tags=MAX_TAGS_PER_MEMORY)
    lines = [header]

    preview = (mem.get('content') or '')[:250].replace('\n', ' ')
    current_tags = mem.get('tags', [])

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
# Core single-memory enrichment
# ---------------------------------------------------------------------------

async def enrich_single(memory_id: str) -> Dict[str, Any]:
    """
    Enrich tags for one memory with a single Gemini LLM call.

    Returns a summary dict with counts of actions taken.
    """
    _log(f"[enrich_single] start {memory_id[:8]}")
    import importlib
    try:
        # Run in a thread — first import takes 3+ seconds and would block the event loop
        _log("[enrich_single] importing google.genai...")
        genai = await asyncio.to_thread(importlib.import_module, 'google.genai')
        genai_types = await asyncio.to_thread(importlib.import_module, 'google.genai.types')
        _log("[enrich_single] import done")
    except ImportError:
        return {'success': False, 'error': 'google-genai not installed'}

    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return {'success': False, 'error': 'GOOGLE_API_KEY not set'}

    # Load memory
    _log("[enrich_single] loading memory from TinyDB")
    memory_db = get_memory_tinydb()
    memories_table = memory_db.table('memories')
    Record = Query()
    rows = memories_table.search(Record.id == memory_id)
    memory_db.close()

    if not rows:
        return {'success': False, 'error': f'Memory {memory_id} not found'}

    mem = rows[0]

    # Build similar_map from the in-process tag registry — one TinyDB read,
    # pure cosine math, no embedding API calls, no event-loop blocking.
    _log("[enrich_single] loading tag registry")
    tags_db = get_tags_tinydb()
    all_tag_records = tags_db.table('tags').all()
    tags_db.close()

    tag_registry_full = {
        r['tag']: {
            'embedding': r.get('embedding', []),
            'usage_count': r.get('usage_count', 0),
        }
        for r in all_tag_records
        if r.get('tag') and r.get('embedding')
    }

    similar_map: Dict[str, List[Dict]] = {}
    for tag in mem.get('tags', []):
        tag_emb = tag_registry_full.get(tag, {}).get('embedding', [])
        if not tag_emb:
            similar_map[tag] = []
            continue
        candidates = []
        for other_tag, other_data in tag_registry_full.items():
            if other_tag == tag:
                continue
            sim = _cosine_similarity(tag_emb, other_data['embedding'])
            if sim >= 0.55:
                candidates.append({
                    'tag': other_tag,
                    'similarity': round(sim, 4),
                    'usage_count': other_data['usage_count'],
                })
        candidates.sort(key=lambda x: (x['similarity'], x['usage_count']), reverse=True)
        similar_map[tag] = candidates[:6]

    prompt = _build_prompt(mem, similar_map)

    _log("[enrich_single] calling Gemini API")
    client = genai.Client(api_key=api_key)
    response = await client.aio.models.generate_content(
        model=ENRICHMENT_LLM_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MemoryTagPatch,
        ),
    )

    patch = MemoryTagPatch.model_validate_json(response.text)

    # Apply patch
    memory_db = get_memory_tinydb()
    memories_table = memory_db.table('memories')

    try:
        tags: List[str] = list(mem.get('tags', []))
        original_tags = list(tags)
        tags_added: List[str] = []
        replaced = 0
        added = 0
        dropped = 0

        # 1. Replacements — hard guardrail enforced independently of LLM judgment
        replaced_out: List[str] = []
        for repl in patch.replacements:
            if repl.old_tag in tags and _replacement_passes_guardrail(repl.old_tag, repl.new_tag):
                tags.remove(repl.old_tag)
                replaced_out.append(repl.old_tag)
                if repl.new_tag not in tags:
                    tags.append(repl.new_tag)
                    increment_tag_usage([repl.new_tag])
                replaced += 1
        decrement_tag_usage(replaced_out)

        # 2. Drops — applied before adds so freed slots can be filled
        dropped_tags: List[str] = []
        for tag in patch.drop:
            if tag in tags and len(tags) - len(dropped_tags) > MIN_TAGS_PER_MEMORY:
                dropped_tags.append(tag)
                dropped += 1
        for tag in dropped_tags:
            tags.remove(tag)
        decrement_tag_usage(dropped_tags)

        # 3. Adds — capped so total never exceeds MAX_TAGS_PER_MEMORY
        slots = max(0, MAX_TAGS_PER_MEMORY - len(tags))

        to_add_existing = [t for t in patch.add_existing if t not in tags][:slots]
        if to_add_existing:
            increment_tag_usage(to_add_existing)
            tags.extend(to_add_existing)
            tags_added.extend(to_add_existing)
            added += len(to_add_existing)
            slots -= len(to_add_existing)

        if patch.add_new and slots > 0:
            await _register_new_tags_async(client, patch.add_new)
            for tag in patch.add_new:
                if tag not in tags and slots > 0:
                    tags.append(tag)
                    tags_added.append(tag)
                    added += 1
                    slots -= 1

        # Write back only if something changed
        if tags != original_tags:
            memories_table.update(
                {'tags': tags, 'last_modified': datetime.now().isoformat()},
                Record.id == memory_id,
            )

        mark_enriched(memory_id, tags_added)
    finally:
        memory_db.close()

    return {
        'success': True,
        'replaced': replaced,
        'added': added,
        'dropped': dropped,
    }


# ---------------------------------------------------------------------------
# Background loop
# ---------------------------------------------------------------------------

async def tag_enrichment_loop(
    interval_short: int = 60,
    interval_long: int = 1200,
) -> None:
    """
    Infinite background loop enriching un-reviewed memory tags one at a time.

    Short sleep (~60 s) after a cycle that found work; long sleep (~20 min) when
    all memories are covered. Start this as an asyncio.Task from the FastMCP lifespan.
    """
    _log("Tag enrichment agent started.")

    sleep_next = interval_short  # first sleep acts as startup grace period
    while True:
        try:
            await asyncio.sleep(sleep_next)
            candidates = get_unenriched_memory_ids(limit=50)

            if candidates:
                _log(f"[tag_enrichment] {len(candidates)} memories to enrich.")
                for memory_id in candidates:
                    result = await enrich_single(memory_id)
                    _log(f"[tag_enrichment] {memory_id[:8]}: {result}")
                    await asyncio.sleep(1)  # yield between API calls
                sleep_next = interval_short
            else:
                sleep_next = interval_long

        except asyncio.CancelledError:
            _log("Tag enrichment agent stopped.")
            raise
        except Exception as exc:
            _log(f"[tag_enrichment] Error: {exc}")
            traceback.print_exc(file=sys.stderr)
            sleep_next = interval_short
