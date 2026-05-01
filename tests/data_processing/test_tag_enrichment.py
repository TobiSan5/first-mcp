#!/usr/bin/env python3
"""
Data Processing Layer Tests — Tag Enrichment Agent (no API, no MCP)

Covers:
  - Enrichment register lifecycle  (mark_enriched, remove_from_enrichment_register,
                                    get_unenriched_memory_ids)
  - Replacement guardrail          (_replacement_passes_guardrail)

All tests use synthetic data and a temp FIRST_MCP_DATA_PATH.
No GOOGLE_API_KEY required — live enrich_batch tests are in
tests/server_intelligence/test_tag_enrichment.py.
"""

import math
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

_TMPDIR = tempfile.mkdtemp()
os.environ['FIRST_MCP_DATA_PATH'] = _TMPDIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit(v):
    n = math.sqrt(sum(x ** 2 for x in v))
    return [x / n for x in v]


def _insert_memory(mid, tags=None, importance=3):
    from first_mcp.memory.database import get_memory_tinydb
    db = get_memory_tinydb()
    db.table('memories').insert({
        'id': mid,
        'content': f'Test memory {mid}',
        'tags': tags or [],
        'importance': importance,
        'created_at': datetime.now().isoformat(),
        'last_modified': datetime.now().isoformat(),
    })
    db.close()


def _insert_tag(tag, embedding, usage_count=1):
    from first_mcp.memory.database import get_tags_tinydb
    db = get_tags_tinydb()
    db.table('tags').insert({
        'tag': tag,
        'embedding': embedding,
        'usage_count': usage_count,
        'created_at': datetime.now().isoformat(),
        'last_used_at': datetime.now().isoformat(),
    })
    db.close()


def _truncate_memories():
    from first_mcp.memory.database import get_memory_tinydb
    db = get_memory_tinydb()
    db.table('memories').truncate()
    db.close()


def _truncate_enriched():
    from first_mcp.memory.database import get_enrichment_tinydb
    db = get_enrichment_tinydb()
    db.table('enriched').truncate()
    db.close()


def _truncate_tags():
    from first_mcp.memory.database import get_tags_tinydb
    db = get_tags_tinydb()
    db.table('tags').truncate()
    db.close()


# ---------------------------------------------------------------------------
# Enrichment register
# ---------------------------------------------------------------------------

class TestEnrichmentRegister(unittest.TestCase):
    """
    Tests for mark_enriched, remove_from_enrichment_register,
    and get_unenriched_memory_ids.
    """

    def setUp(self):
        _truncate_memories()
        _truncate_enriched()
        from first_mcp.memory.tag_enrichment import (
            mark_enriched,
            remove_from_enrichment_register,
            get_unenriched_memory_ids,
        )
        self.mark = mark_enriched
        self.remove = remove_from_enrichment_register
        self.unenriched = get_unenriched_memory_ids

    def test_fresh_memories_are_all_unenriched(self):
        """Newly inserted memories appear in the unenriched list."""
        _insert_memory('a')
        _insert_memory('b')
        ids = self.unenriched(limit=10)
        self.assertIn('a', ids)
        self.assertIn('b', ids)

    def test_mark_removes_from_unenriched(self):
        """After marking, the memory no longer appears in the unenriched list."""
        _insert_memory('a')
        _insert_memory('b')
        self.mark('a', tags_added=['tag1'])
        ids = self.unenriched(limit=10)
        self.assertNotIn('a', ids)
        self.assertIn('b', ids)

    def test_remove_re_queues_memory(self):
        """remove_from_enrichment_register puts a memory back into the unenriched queue."""
        _insert_memory('a')
        self.mark('a', tags_added=[])
        self.assertNotIn('a', self.unenriched(limit=10))

        self.remove('a')
        self.assertIn('a', self.unenriched(limit=10))

    def test_remove_nonexistent_is_silent(self):
        """Removing an ID that is not in the register raises no exception."""
        try:
            self.remove('ghost-id-xyz')
        except Exception as e:
            self.fail(f"remove_from_enrichment_register raised unexpectedly: {e}")

    def test_limit_is_respected(self):
        """get_unenriched_memory_ids returns at most `limit` IDs."""
        for i in range(6):
            _insert_memory(str(i))
        ids = self.unenriched(limit=3)
        self.assertEqual(len(ids), 3)

    def test_empty_database_returns_empty_list(self):
        """No memories in the DB → empty unenriched list."""
        self.assertEqual(self.unenriched(limit=10), [])

    def test_all_enriched_returns_empty_list(self):
        """When every memory is already enriched, the list is empty."""
        _insert_memory('x')
        self.mark('x', tags_added=[])
        self.assertEqual(self.unenriched(limit=10), [])

    def test_mark_records_tags_added(self):
        """tags_added passed to mark_enriched is stored in the register."""
        from first_mcp.memory.database import get_enrichment_tinydb
        from tinydb import Query
        _insert_memory('r')
        self.mark('r', tags_added=['new-tag', 'another-tag'])
        db = get_enrichment_tinydb()
        rows = db.table('enriched').search(Query().memory_id == 'r')
        db.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['tags_added'], ['new-tag', 'another-tag'])


# ---------------------------------------------------------------------------
# Replacement guardrail
# ---------------------------------------------------------------------------

class TestReplacementGuardrail(unittest.TestCase):
    """
    Tests for _replacement_passes_guardrail with synthetic tag embeddings.

    Guardrail passes only when BOTH conditions hold:
      1. cosine_similarity(old, new) > REPLACEMENT_SIMILARITY_THRESHOLD (0.85)
      2. new_tag.usage_count > old_tag.usage_count
    """

    def setUp(self):
        _truncate_tags()
        from first_mcp.memory.tag_enrichment import (
            _replacement_passes_guardrail,
            REPLACEMENT_SIMILARITY_THRESHOLD,
        )
        self.guardrail = _replacement_passes_guardrail
        self.threshold = REPLACEMENT_SIMILARITY_THRESHOLD

    def test_high_sim_and_higher_usage_passes(self):
        """Both conditions met → guardrail passes."""
        # Angle ≈ 8°, cos ≈ 0.99 — well above 0.85
        e_old = _unit([1.0, 0.0, 0.0])
        e_new = _unit([0.99, 0.14, 0.0])
        _insert_tag('old-tag', e_old, usage_count=2)
        _insert_tag('new-tag', e_new, usage_count=10)
        self.assertTrue(self.guardrail('old-tag', 'new-tag'))

    def test_low_similarity_rejects(self):
        """Low cosine similarity → rejected even when new tag has more uses."""
        e_old = _unit([1.0, 0.0, 0.0])
        e_new = _unit([0.0, 1.0, 0.0])  # cos = 0 — orthogonal
        _insert_tag('old-tag', e_old, usage_count=1)
        _insert_tag('new-tag', e_new, usage_count=99)
        self.assertFalse(self.guardrail('old-tag', 'new-tag'))

    def test_equal_usage_count_rejects(self):
        """New tag with same usage count as old → rejected (must be strictly greater)."""
        e = _unit([1.0, 0.0, 0.0])
        _insert_tag('old-tag', e, usage_count=5)
        _insert_tag('new-tag', e, usage_count=5)
        self.assertFalse(self.guardrail('old-tag', 'new-tag'))

    def test_lower_usage_count_rejects(self):
        """New tag with fewer uses → rejected regardless of similarity."""
        e_old = _unit([1.0, 0.0, 0.0])
        e_new = _unit([0.99, 0.14, 0.0])
        _insert_tag('old-tag', e_old, usage_count=20)
        _insert_tag('new-tag', e_new, usage_count=3)
        self.assertFalse(self.guardrail('old-tag', 'new-tag'))

    def test_missing_old_tag_rejects(self):
        """old_tag not in registry → False (no crash)."""
        e = _unit([1.0, 0.0, 0.0])
        _insert_tag('new-tag', e, usage_count=5)
        self.assertFalse(self.guardrail('ghost-old', 'new-tag'))

    def test_missing_new_tag_rejects(self):
        """new_tag not in registry → False (no crash)."""
        e = _unit([1.0, 0.0, 0.0])
        _insert_tag('old-tag', e, usage_count=1)
        self.assertFalse(self.guardrail('old-tag', 'ghost-new'))

    def test_empty_embedding_rejects(self):
        """Tag with empty embedding [] → False (cannot compute similarity)."""
        e = _unit([1.0, 0.0, 0.0])
        _insert_tag('old-tag', [], usage_count=1)
        _insert_tag('new-tag', e, usage_count=5)
        self.assertFalse(self.guardrail('old-tag', 'new-tag'))

    def test_similarity_just_below_threshold_rejects(self):
        """
        Similarity just below REPLACEMENT_SIMILARITY_THRESHOLD (0.85) must
        be rejected even when new tag has higher usage count.

        Construct v2 = (0.84, sin, 0) so cos(v1, v2) ≈ 0.84 < 0.85.
        """
        from first_mcp.embeddings import cosine_similarity
        t = 0.84  # just below threshold 0.85
        e_old = _unit([1.0, 0.0, 0.0])
        e_new = _unit([t, math.sqrt(max(0.0, 1 - t ** 2)), 0.0])
        actual_sim = cosine_similarity(e_old, e_new)
        self.assertLess(actual_sim, self.threshold,
                        f"Test setup error: sim {actual_sim:.4f} must be < {self.threshold}")
        _insert_tag('old-tag', e_old, usage_count=1)
        _insert_tag('new-tag', e_new, usage_count=5)
        self.assertFalse(self.guardrail('old-tag', 'new-tag'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
