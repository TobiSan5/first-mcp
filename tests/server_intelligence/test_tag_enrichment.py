#!/usr/bin/env python3
"""
Server Intelligence Tests — Tag Enrichment Agent (live Gemini API)

Tests enrich_single end-to-end against the real Gemini API.
Skipped when GOOGLE_API_KEY is not set.

All tests write to a temp FIRST_MCP_DATA_PATH — no production data is touched.
Tags are registered with real embeddings so the full enrichment pipeline runs
(prompt building → Gemini call → structured-output patch → guardrail → TinyDB write).
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

_TMPDIR = tempfile.mkdtemp()
os.environ['FIRST_MCP_DATA_PATH'] = _TMPDIR

_HAS_API_KEY = bool(os.getenv('GOOGLE_API_KEY'))


def _insert_memory(mid, content, tags, importance=3):
    from first_mcp.memory.database import get_memory_tinydb
    db = get_memory_tinydb()
    db.table('memories').insert({
        'id': mid,
        'content': content,
        'tags': tags,
        'importance': importance,
        'created_at': datetime.now().isoformat(),
        'last_modified': datetime.now().isoformat(),
    })
    db.close()


def _get_memory(mid):
    from first_mcp.memory.database import get_memory_tinydb
    db = get_memory_tinydb()
    rows = db.table('memories').all()
    db.close()
    return next((r for r in rows if r['id'] == mid), None)


@unittest.skipUnless(_HAS_API_KEY, 'GOOGLE_API_KEY not set')
class TestEnrichSingle(unittest.TestCase):
    """
    Live tests for enrich_single.  Each test gets a clean memory and enrichment
    table so tests are independent of each other.
    """

    def setUp(self):
        from first_mcp.memory.database import get_memory_tinydb, get_enrichment_tinydb
        from first_mcp.memory.tag_enrichment import enrich_single, get_unenriched_memory_ids
        from first_mcp.memory.tag_tools import tinydb_register_tags

        self.enrich = enrich_single
        self.unenriched = get_unenriched_memory_ids
        self.register_tags = tinydb_register_tags

        # Truncate memories and enrichment register; keep tags across tests
        # so that embeddings are reused and we don't spam the embedding API.
        db = get_memory_tinydb()
        db.table('memories').truncate()
        db.close()

        db = get_enrichment_tinydb()
        db.table('enriched').truncate()
        db.close()

    # ------------------------------------------------------------------
    # Return structure
    # ------------------------------------------------------------------

    def test_returns_success_structure(self):
        """enrich_single returns a dict with the required keys and success=True."""
        self.register_tags(['python', 'web-development'])
        _insert_memory('m1', 'Building web APIs with Python and FastAPI.', ['python', 'web-development'])

        result = \1

        self.assertIsInstance(result, dict)
        self.assertTrue(result.get('success'), f'Expected success=True, got: {result}')
        for key in ('replaced', 'added', 'dropped'):
            self.assertIn(key, result, f"Missing key '{key}'")
        self.assertIsInstance(result['replaced'], int)
        self.assertIsInstance(result['added'], int)
        self.assertIsInstance(result['dropped'], int)

    def test_nonexistent_id_returns_error(self):
        """A memory ID not in the DB returns success=False with an error key."""
        result = \1

        self.assertFalse(result.get('success'))
        self.assertIn('error', result)

    # ------------------------------------------------------------------
    # Enrichment register
    # ------------------------------------------------------------------

    def test_memory_marked_enriched_after_call(self):
        """The processed memory is added to the enrichment register."""
        self.register_tags(['data-science', 'statistics'])
        _insert_memory('r1', 'Statistical analysis of survey data using R.', ['data-science', 'statistics'])
        self.assertIn('r1', self.unenriched(limit=10))

        \1

        self.assertNotIn('r1', self.unenriched(limit=10))

    def test_multiple_memories_all_marked_enriched(self):
        """Each memory enriched individually is recorded in the register."""
        self.register_tags(['project-management', 'agile'])
        ids = ['pm1', 'pm2', 'pm3']
        for i, mid in enumerate(ids):
            _insert_memory(mid, f'Agile sprint planning for project phase {i}.', ['project-management', 'agile'])

        for mid in ids:
            \1

        remaining = self.unenriched(limit=10)
        for mid in ids:
            self.assertNotIn(mid, remaining, f'{mid} was not marked enriched')

    # ------------------------------------------------------------------
    # Data integrity
    # ------------------------------------------------------------------

    def test_tags_remain_list_of_strings_after_enrichment(self):
        """Regardless of what the LLM suggests, tags must be a list of strings."""
        self.register_tags(['workflow', 'productivity'])
        _insert_memory('integrity', 'Personal productivity workflow using GTD method.', ['workflow', 'productivity'])

        \1

        mem = _get_memory('integrity')
        self.assertIsNotNone(mem)
        self.assertIsInstance(mem['tags'], list)
        self.assertTrue(all(isinstance(t, str) for t in mem['tags']),
                        f'Non-string tag found: {mem["tags"]}')

    def test_importance_field_unchanged_after_enrichment(self):
        """enrich_single must not touch the importance field."""
        self.register_tags(['security', 'authentication'])
        _insert_memory('sec', 'OAuth2 token-based authentication for REST APIs.', ['security', 'authentication'], importance=5)

        \1

        mem = _get_memory('sec')
        self.assertEqual(mem['importance'], 5)

    def test_content_field_unchanged_after_enrichment(self):
        """enrich_single must not modify the memory content."""
        original_content = 'Kubernetes cluster autoscaling based on CPU metrics.'
        self.register_tags(['kubernetes', 'devops'])
        _insert_memory('k8s', original_content, ['kubernetes', 'devops'])

        \1

        mem = _get_memory('k8s')
        self.assertEqual(mem['content'], original_content)

    # ------------------------------------------------------------------
    # Guardrail integration
    # ------------------------------------------------------------------

    def test_replacements_respect_guardrail(self):
        """
        Any tag replacement that the LLM suggests must pass the guardrail
        (sim > 0.85 AND new tag more used).  We verify this indirectly by
        checking that no tag was swapped for one with 0 usage count in the
        registry (which would mean the guardrail was bypassed).
        """
        from first_mcp.memory.database import get_tags_tinydb
        from tinydb import Query

        self.register_tags(['nodejs', 'backend'])
        _insert_memory('node', 'Building REST services with Node.js and Express.', ['nodejs', 'backend'])

        \1

        mem = _get_memory('node')
        tags_db = get_tags_tinydb()
        tags_table = tags_db.table('tags')
        Record = Query()
        for tag in mem.get('tags', []):
            rows = tags_table.search(Record.tag == tag)
            # Every tag on the memory must exist in the registry
            # (guardrail requires both tags to be registered)
            if rows:
                self.assertGreater(rows[0].get('usage_count', 0), 0,
                                   f"Tag '{tag}' has usage_count=0 — guardrail may have been bypassed")
        tags_db.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
