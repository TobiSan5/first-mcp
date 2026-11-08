#!/usr/bin/env python3
"""
Data Processing Tests — v2 TaggingEngine and tag suggesters

Pure logic tests: a deterministic fake embedder (no fastembed model, no API)
and a SQLite store in a temp directory. Covers:
  - normalize_tags (list / comma string / invalid / dedupe)
  - client-suggested tags stored without any LLM
  - client tag resolved to a semantically close existing tag
  - no tags + no suggester → empty tag set + warning
  - optional suggester: used, merged after client tags, failure tolerated
  - retag_on_update keep/replace rules
  - get_tag_suggester_from_env configuration handling
"""

import hashlib
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

_DIM = 384


def _unit(v: np.ndarray) -> np.ndarray:
    return (v / np.linalg.norm(v)).astype(np.float32)


def _hash_vec(text: str) -> np.ndarray:
    seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "little")
    return _unit(np.random.default_rng(seed).standard_normal(_DIM))


class FakeEmbedder:
    """Random-but-deterministic unit vectors; selected texts made near-identical."""

    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        # alias -> base text: alias gets a vector very close to the base's
        self._aliases = aliases or {}

    @property
    def model_name(self) -> str:
        return "fake-embedder"

    @property
    def dimensions(self) -> int:
        return _DIM

    def embed(self, texts):
        out = []
        for t in texts:
            if not t.strip():
                out.append(None)
            elif t in self._aliases:
                base = _hash_vec(self._aliases[t])
                out.append(_unit(base + 0.1 * _hash_vec("noise:" + t)))  # cos ≈ 0.995
            else:
                out.append(_hash_vec(t))
        return out


class FakeSuggester:
    def __init__(self, tags=None, exc=None) -> None:
        self.tags, self.exc, self.calls = tags or [], exc, 0

    @property
    def name(self) -> str:
        return "fake:model"

    def suggest(self, content):
        self.calls += 1
        if self.exc:
            raise self.exc
        return list(self.tags)


class _EngineTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from first_mcp.storage.sqlite_storage import SQLiteStorageStrategy
        from first_mcp.storage.protocols import MemoryRecord
        self.MemoryRecord = MemoryRecord
        self.storage = SQLiteStorageStrategy(os.path.join(self.tmp, "t.db"))

    def tearDown(self):
        self.storage.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def engine(self, aliases=None, suggester=None):
        from first_mcp.storage.tagging_engine import TaggingEngine
        return TaggingEngine(self.storage, FakeEmbedder(aliases), suggester=suggester)

    def add_memory(self, mid, content="some content"):
        self.storage.store_memory(self.MemoryRecord(id=mid, content=content))


class TestNormalizeTags(unittest.TestCase):
    def setUp(self):
        from first_mcp.storage.tagging_engine import normalize_tags
        self.normalize = normalize_tags

    def test_none(self):
        self.assertEqual(self.normalize(None), ([], []))

    def test_comma_string(self):
        self.assertEqual(self.normalize("Home Alarm, car-repair ,"),
                         (["home_alarm", "car_repair"], []))

    def test_list_dedupes_after_normalisation(self):
        self.assertEqual(self.normalize(["Home Alarm", "home_alarm", "home-alarm"]),
                         (["home_alarm"], []))

    def test_invalid_rejected(self):
        valid, rejected = self.normalize(["2024", "!!!", "ok_tag"])
        self.assertEqual(valid, ["ok_tag"])
        self.assertEqual(rejected, ["2024", "!!!"])


class TestClientTagsWithoutLLM(_EngineTestBase):
    def test_client_tags_applied_as_new(self):
        self.add_memory("m1")
        r = self.engine().tag_memory("m1", "content", ["home_alarm", "Car Repair"])
        self.assertEqual(r.tags, ["home_alarm", "car_repair"])
        self.assertEqual(r.warnings, [])
        self.assertEqual([x["matched_existing"] for x in r.resolution], [False, False])
        self.assertEqual({x["source"] for x in r.resolution}, {"client"})
        self.assertEqual(sorted(self.storage.get_tags_for_memory("m1")),
                         ["car_repair", "home_alarm"])
        self.assertEqual(self.storage.get_tag("home_alarm").usage_count, 1)

    def test_client_tag_maps_to_close_existing_tag(self):
        eng = self.engine(aliases={"house_alarm": "home_alarm"})
        self.add_memory("m1")
        self.add_memory("m2")
        eng.tag_memory("m1", "first", ["home_alarm"])
        r = eng.tag_memory("m2", "second", ["house_alarm"])
        self.assertEqual(r.tags, ["home_alarm"])
        self.assertEqual(r.resolution, [{"suggested": "house_alarm", "applied": "home_alarm",
                                         "matched_existing": True, "source": "client"}])
        self.assertIsNone(self.storage.get_tag("house_alarm"))
        self.assertEqual(self.storage.get_tag("home_alarm").usage_count, 2)

    def test_unrelated_tag_not_merged(self):
        eng = self.engine()
        self.add_memory("m1")
        self.add_memory("m2")
        eng.tag_memory("m1", "a", ["home_alarm"])
        r = eng.tag_memory("m2", "b", ["gardening"])
        self.assertEqual(r.tags, ["gardening"])

    def test_no_tags_no_suggester_warns(self):
        from first_mcp.storage.tagging_engine import NO_TAGS_WARNING
        self.add_memory("m1")
        r = self.engine().tag_memory("m1", "content")
        self.assertEqual(r.tags, [])
        self.assertIn(NO_TAGS_WARNING, r.warnings)

    def test_invalid_tags_reported(self):
        self.add_memory("m1")
        r = self.engine().tag_memory("m1", "content", ["2024", "valid_tag"])
        self.assertEqual(r.tags, ["valid_tag"])
        self.assertTrue(any("2024" in w for w in r.warnings))


class TestOptionalSuggester(_EngineTestBase):
    def test_suggester_tags_follow_client_tags(self):
        s = FakeSuggester(tags=["Extra Topic", "home_alarm"])
        self.add_memory("m1")
        r = self.engine(suggester=s).tag_memory("m1", "content", ["home_alarm"])
        self.assertEqual(s.calls, 1)
        self.assertEqual(r.tags, ["home_alarm", "extra_topic"])
        self.assertEqual([x["source"] for x in r.resolution], ["client", "suggester"])

    def test_suggester_failure_does_not_block_write(self):
        s = FakeSuggester(exc=RuntimeError("quota exceeded"))
        self.add_memory("m1")
        r = self.engine(suggester=s).tag_memory("m1", "content", ["home_alarm"])
        self.assertEqual(r.tags, ["home_alarm"])
        self.assertTrue(any("fake:model failed" in w for w in r.warnings))


class TestRetagOnUpdate(_EngineTestBase):
    def test_content_change_without_tags_keeps_tags(self):
        eng = self.engine()
        self.add_memory("m1")
        eng.tag_memory("m1", "old", ["home_alarm"])
        self.assertIsNone(eng.retag_on_update("m1", "new content", None))
        self.assertEqual(self.storage.get_tags_for_memory("m1"), ["home_alarm"])

    def test_tags_given_replace_and_fix_usage(self):
        eng = self.engine()
        self.add_memory("m1")
        eng.tag_memory("m1", "old", ["home_alarm"])
        r = eng.retag_on_update("m1", None, "gardening")
        self.assertEqual(r.tags, ["gardening"])
        self.assertEqual(self.storage.get_tags_for_memory("m1"), ["gardening"])
        self.assertEqual(self.storage.get_tag("home_alarm").usage_count, 0)

    def test_content_change_with_suggester_regenerates(self):
        s = FakeSuggester(tags=["new_topic"])
        eng = self.engine(suggester=s)
        self.add_memory("m1")
        eng.tag_memory("m1", "old", ["home_alarm"])
        r = eng.retag_on_update("m1", "new content", None)
        self.assertIn("new_topic", r.tags)


class TestSuggesterFromEnv(unittest.TestCase):
    _KEYS = ("FIRST_MCP_TAG_SUGGESTER", "GOOGLE_API_KEY", "FIRST_MCP_TAGGING_MODEL")

    def setUp(self):
        self._saved = {k: os.environ.pop(k, None) for k in self._KEYS}
        from first_mcp.storage.tag_suggesters import get_tag_suggester_from_env
        self.get = get_tag_suggester_from_env

    def tearDown(self):
        for k, v in self._saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    def test_default_is_none_even_with_google_key(self):
        os.environ["GOOGLE_API_KEY"] = "dummy"
        self.assertIsNone(self.get())

    def test_explicit_none(self):
        os.environ["FIRST_MCP_TAG_SUGGESTER"] = "none"
        self.assertIsNone(self.get())

    def test_unknown_value_is_none(self):
        os.environ["FIRST_MCP_TAG_SUGGESTER"] = "some_vendor"
        self.assertIsNone(self.get())

    def test_gemini_without_key_is_none(self):
        os.environ["FIRST_MCP_TAG_SUGGESTER"] = "gemini"
        self.assertIsNone(self.get())

    def test_gemini_with_key(self):
        import importlib.util
        if importlib.util.find_spec("google.genai") is None:
            self.skipTest("google-genai not installed")
        os.environ["FIRST_MCP_TAG_SUGGESTER"] = "gemini"
        os.environ["GOOGLE_API_KEY"] = "dummy"
        os.environ["FIRST_MCP_TAGGING_MODEL"] = "gemini-x"
        s = self.get()
        self.assertEqual(s.name, "gemini:gemini-x")  # constructed lazily, no API call


if __name__ == "__main__":
    unittest.main(verbosity=2)
