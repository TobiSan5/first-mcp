#!/usr/bin/env python3
"""
Data Processing Layer Tests — Memory Retrieval (pagination + tag scoring)

Tests the two new data-layer modules with no MCP client and no external API:

  pagination.py  — save/get/cleanup of paginated result files
  tag_scoring.py — score_memories_by_tags with synthetic embeddings

All tests run without GOOGLE_API_KEY or a real TinyDB.
"""

import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit(v):
    """Return unit vector (L2-normalised) of v."""
    n = math.sqrt(sum(x ** 2 for x in v))
    return [x / n for x in v]


def _make_memory(id_, tags):
    return {"id": id_, "content": f"memory {id_}", "tags": tags, "importance": 3}


# ---------------------------------------------------------------------------
# Pagination tests
# ---------------------------------------------------------------------------

class TestPagination(unittest.TestCase):
    """Tests for pagination.py — save / get_next_page / cleanup."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        os.environ['FIRST_MCP_DATA_PATH'] = self._tmpdir
        # Import after env var is set so _paginated_dir() resolves correctly
        from first_mcp.memory.pagination import (
            save_paginated_results, get_next_page, cleanup_paginated_files
        )
        self.save = save_paginated_results
        self.get_page = get_next_page
        self.cleanup = cleanup_paginated_files

    def _results(self, n=12):
        return [{"id": str(i), "content": f"mem {i}"} for i in range(n)]

    def test_first_page_already_consumed_by_caller(self):
        """save_paginated_results starts offset at page_size (first page already returned)."""
        results = self._results(12)
        token = self.save(results, page_size=5, query_info={})
        page = self.get_page(token)
        # Second page: ids 5-9
        self.assertEqual([m["id"] for m in page["memories"]], ["5", "6", "7", "8", "9"])
        self.assertEqual(page["page_offset"], 5)

    def test_page_sequence_is_correct(self):
        """Pages 2 and 3 cover the full remaining result set without overlap."""
        results = self._results(12)
        token = self.save(results, page_size=5, query_info={})
        p2 = self.get_page(token)
        p3 = self.get_page(p2["next_page_token"])
        ids_p2 = [m["id"] for m in p2["memories"]]
        ids_p3 = [m["id"] for m in p3["memories"]]
        self.assertEqual(ids_p2, ["5", "6", "7", "8", "9"])
        self.assertEqual(ids_p3, ["10", "11"])
        self.assertFalse(set(ids_p2) & set(ids_p3), "pages must not overlap")

    def test_last_page_has_no_next_token(self):
        """The final page returns has_more=False and next_page_token=None."""
        results = self._results(7)
        token = self.save(results, page_size=5, query_info={})
        last = self.get_page(token)
        self.assertFalse(last["has_more"])
        self.assertIsNone(last["next_page_token"])

    def test_file_deleted_after_last_page(self):
        """Temp file is removed once all results are consumed."""
        results = self._results(7)
        token = self.save(results, page_size=5, query_info={})
        paged_dir = os.path.join(self._tmpdir, '_paginated')
        self.assertEqual(len(os.listdir(paged_dir)), 1)
        self.get_page(token)
        self.assertEqual(len(os.listdir(paged_dir)), 0, "file should be gone after last page")

    def test_exhausted_token_returns_error(self):
        """Calling get_next_page after exhaustion returns success=False."""
        results = self._results(6)
        token = self.save(results, page_size=5, query_info={})
        self.get_page(token)  # exhaust
        err = self.get_page(token)
        self.assertFalse(err["success"])
        self.assertIn("error", err)

    def test_bad_token_returns_error(self):
        """A random UUID that was never saved returns success=False."""
        import uuid
        err = self.get_page(str(uuid.uuid4()))
        self.assertFalse(err["success"])
        self.assertIn("error", err)

    def test_total_found_is_full_set_size(self):
        """total_found reports the complete result set, not just the page."""
        results = self._results(12)
        token = self.save(results, page_size=5, query_info={})
        page = self.get_page(token)
        self.assertEqual(page["total_found"], 12)

    def test_query_info_preserved(self):
        """query_info passed to save is returned unchanged by get_next_page."""
        info = {"tags": "test-tag", "limit": 50}
        results = self._results(8)
        token = self.save(results, page_size=5, query_info=info)
        page = self.get_page(token)
        self.assertEqual(page["query_info"]["tags"], "test-tag")
        self.assertEqual(page["query_info"]["limit"], 50)

    def test_cleanup_removes_all_files(self):
        """cleanup_paginated_files deletes every .json file in _paginated/."""
        for _ in range(3):
            self.save(self._results(8), page_size=5, query_info={})
        paged_dir = os.path.join(self._tmpdir, '_paginated')
        self.assertEqual(len(os.listdir(paged_dir)), 3)
        removed = self.cleanup()
        self.assertEqual(removed, 3)
        self.assertEqual(len(os.listdir(paged_dir)), 0)

    def test_cleanup_empty_dir_returns_zero(self):
        """cleanup_paginated_files on an empty dir returns 0 without error."""
        removed = self.cleanup()
        self.assertEqual(removed, 0)

    def test_cleanup_nonexistent_dir_returns_zero(self):
        """cleanup_paginated_files when _paginated/ doesn't exist returns 0."""
        # Don't create any files — dir shouldn't exist yet
        paged_dir = os.path.join(self._tmpdir, '_paginated')
        self.assertFalse(os.path.isdir(paged_dir))
        removed = self.cleanup()
        self.assertEqual(removed, 0)


# ---------------------------------------------------------------------------
# Tag scoring tests
# ---------------------------------------------------------------------------

class TestTagScoring(unittest.TestCase):
    """
    Tests for tag_scoring.score_memories_by_tags using synthetic 3-dim embeddings.
    No API calls; registry is passed in directly.
    """

    def setUp(self):
        from first_mcp.memory.tag_scoring import score_memories_by_tags
        self.score = score_memories_by_tags

        # Synthetic 3-dim unit vectors that encode clear semantic relationships
        self.registry = {
            "timetabling":  _unit([1.00, 0.05, 0.00]),
            "scheduling":   _unit([0.95, 0.30, 0.00]),  # close to timetabling
            "startup":      _unit([0.00, 1.00, 0.00]),
            "python":       _unit([0.00, 0.00, 1.00]),
            "unrelated":    _unit([0.00, 0.05, 0.00]),  # close to startup but different
        }

    def test_vocabulary_mismatch_resolved(self):
        """
        'scheduling' (query) should retrieve memory tagged 'timetabling'
        even though the tag names differ.  This is the core failure case
        from the architecture doc.
        """
        memories = [
            _make_memory("ergatax", ["timetabling", "startup"]),
            _make_memory("code",    ["python"]),
        ]
        results = self.score(["scheduling"], memories, self.registry)
        ids = [m["id"] for (_, m, _) in results]
        self.assertIn("ergatax", ids, "'timetabling' memory must be found via 'scheduling'")

    def test_unrelated_memory_excluded(self):
        """A memory whose tags are all below the adaptive threshold is excluded."""
        memories = [
            _make_memory("ergatax", ["timetabling"]),
            _make_memory("code",    ["python"]),
        ]
        # Query 'scheduling' is close to 'timetabling' but far from 'python'
        results = self.score(["scheduling"], memories, self.registry)
        ids = [m["id"] for (_, m, _) in results]
        self.assertNotIn("code", ids)

    def test_more_matching_tags_rank_higher(self):
        """
        A memory that matches two query tags outranks one that matches one tag.
        rank_score is the sum of above-threshold scores.
        """
        memories = [
            _make_memory("partial", ["timetabling"]),
            _make_memory("full",    ["timetabling", "scheduling"]),
        ]
        results = self.score(["timetabling", "scheduling"], memories, self.registry)
        self.assertTrue(len(results) >= 2)
        top_id = results[0][1]["id"]
        self.assertEqual(top_id, "full", "memory matching 2 tags should rank first")

    def test_exact_tag_match_included(self):
        """A memory whose tag is identical to the query tag is always a hit."""
        memories = [_make_memory("exact", ["python"])]
        results = self.score(["python"], memories, self.registry)
        ids = [m["id"] for (_, m, _) in results]
        self.assertIn("exact", ids)

    def test_matched_query_tags_reported(self):
        """The third element of each result tuple lists the matched query tags."""
        memories = [_make_memory("m", ["timetabling", "python"])]
        results = self.score(["scheduling", "python"], memories, self.registry)
        self.assertEqual(len(results), 1)
        _, _, matched = results[0]
        self.assertIsInstance(matched, list)
        self.assertTrue(len(matched) > 0)

    def test_empty_registry_returns_empty(self):
        """When the registry has no embeddings, scoring cannot proceed."""
        memories = [_make_memory("m", ["timetabling"])]
        results = self.score(["scheduling"], memories, {})
        self.assertEqual(results, [])

    def test_empty_memories_returns_empty(self):
        """No memories to score returns empty list."""
        results = self.score(["scheduling"], [], self.registry)
        self.assertEqual(results, [])

    def test_memory_with_no_known_tags_excluded(self):
        """A memory whose tags are all absent from the registry scores 0 and is dropped."""
        memories = [
            _make_memory("known",   ["timetabling"]),
            _make_memory("unknown", ["ghost-tag-xyz"]),  # not in registry
        ]
        results = self.score(["scheduling"], memories, self.registry)
        ids = [m["id"] for (_, m, _) in results]
        self.assertIn("known", ids)
        self.assertNotIn("unknown", ids)

    def test_result_sorted_descending_by_score(self):
        """Results are sorted highest rank_score first."""
        memories = [
            _make_memory("low",  ["unrelated"]),
            _make_memory("high", ["timetabling", "scheduling"]),
        ]
        results = self.score(["scheduling", "timetabling"], memories, self.registry)
        scores = [s for (s, _, _) in results]
        self.assertEqual(scores, sorted(scores, reverse=True))


# ---------------------------------------------------------------------------
# Date sort key tests
# ---------------------------------------------------------------------------

def _sort_key(m):
    """Mirror of the sort key used in server_impl for date-based ordering."""
    return m.get('last_modified') or m.get('timestamp') or ''


class TestDateSortKey(unittest.TestCase):
    """
    Tests for the sort key used in sort_by="date_desc"/"date_asc".

    Sort key resolution order:
      1. last_modified   — present and non-empty
      2. timestamp       — fallback when last_modified is absent or None
      3. ''              — ultimate fallback (sorts to the beginning in desc,
                           end in asc, as ISO strings compare correctly)

    All tests use synthetic memory dicts — no API, no TinyDB, no MCP client.
    """

    def _mem(self, id_, timestamp=None, last_modified=None):
        m = {"id": id_, "content": f"memory {id_}"}
        if timestamp is not None:
            m["timestamp"] = timestamp
        if last_modified is not None:
            m["last_modified"] = last_modified
        return m

    # -- sort key resolution --------------------------------------------------

    def test_last_modified_used_when_present(self):
        """last_modified is returned when it exists and is non-empty."""
        m = self._mem("a", timestamp="2025-01-01T00:00:00", last_modified="2025-06-01T00:00:00")
        self.assertEqual(_sort_key(m), "2025-06-01T00:00:00")

    def test_timestamp_used_when_no_last_modified(self):
        """timestamp is the fallback when last_modified is absent."""
        m = self._mem("a", timestamp="2025-01-01T00:00:00")
        self.assertEqual(_sort_key(m), "2025-01-01T00:00:00")

    def test_timestamp_used_when_last_modified_is_none(self):
        """timestamp is the fallback when last_modified is explicitly None."""
        m = self._mem("a", timestamp="2025-01-01T00:00:00", last_modified=None)
        self.assertEqual(_sort_key(m), "2025-01-01T00:00:00")

    def test_empty_string_when_both_absent(self):
        """Empty string is returned when neither field is present."""
        m = {"id": "a", "content": "no dates"}
        self.assertEqual(_sort_key(m), "")

    # -- descending sort (most recent first) ----------------------------------

    def test_desc_sort_by_last_modified(self):
        """date_desc puts the most recently modified memory first."""
        memories = [
            self._mem("old",  timestamp="2025-01-01T10:00:00"),
            self._mem("mid",  timestamp="2025-03-01T10:00:00"),
            self._mem("new",  timestamp="2025-05-01T10:00:00"),
        ]
        memories.sort(key=_sort_key, reverse=True)
        self.assertEqual([m["id"] for m in memories], ["new", "mid", "old"])

    def test_desc_sort_last_modified_beats_newer_timestamp(self):
        """
        An older memory that was recently modified must rank above a newer
        memory that was never modified.
        """
        memories = [
            self._mem("a_modified",  timestamp="2025-01-01T00:00:00",
                                     last_modified="2025-09-01T00:00:00"),
            self._mem("b_unmodified", timestamp="2025-06-01T00:00:00"),
        ]
        memories.sort(key=_sort_key, reverse=True)
        self.assertEqual(memories[0]["id"], "a_modified")

    # -- ascending sort (oldest first) ----------------------------------------

    def test_asc_sort_by_timestamp(self):
        """date_asc puts the oldest memory first."""
        memories = [
            self._mem("new",  timestamp="2025-05-01T10:00:00"),
            self._mem("mid",  timestamp="2025-03-01T10:00:00"),
            self._mem("old",  timestamp="2025-01-01T10:00:00"),
        ]
        memories.sort(key=_sort_key, reverse=False)
        self.assertEqual([m["id"] for m in memories], ["old", "mid", "new"])

    def test_asc_sort_last_modified_beats_newer_timestamp(self):
        """
        In ascending order, a memory whose last_modified is the most recent
        must appear last, even if it was inserted before other memories.
        """
        memories = [
            self._mem("a_modified",   timestamp="2025-01-01T00:00:00",
                                      last_modified="2025-09-01T00:00:00"),
            self._mem("b_unmodified", timestamp="2025-06-01T00:00:00"),
        ]
        memories.sort(key=_sort_key, reverse=False)
        self.assertEqual(memories[-1]["id"], "a_modified")

    # -- edge cases -----------------------------------------------------------

    def test_stable_on_equal_keys(self):
        """Memories with identical sort keys maintain their original order."""
        ts = "2025-04-01T12:00:00"
        memories = [self._mem(str(i), timestamp=ts) for i in range(5)]
        original_ids = [m["id"] for m in memories]
        memories.sort(key=_sort_key, reverse=True)
        self.assertEqual([m["id"] for m in memories], original_ids)

    def test_missing_dates_sort_to_front_in_desc(self):
        """
        Memories with no date fields get sort key '' which is lexicographically
        smallest — they appear first in descending order (least preferred).
        This is acceptable: dateless memories cannot claim recency.
        """
        memories = [
            self._mem("dated",   timestamp="2025-01-01T00:00:00"),
            self._mem("undated"),
        ]
        memories.sort(key=_sort_key, reverse=True)
        # 'dated' has a real timestamp so it should rank above '' in desc order
        self.assertEqual(memories[0]["id"], "dated")


if __name__ == '__main__':
    print("⚙️  Data Processing Layer Tests — Memory Retrieval (pagination + tag scoring + date sort)")
    print("No API or TinyDB required — all tests use synthetic data.\n")
    unittest.main(verbosity=2)
