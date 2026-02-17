#!/usr/bin/env python3
"""
Data Processing Layer Tests — workspace edit

Tests WorkspaceManager.edit_text_file() directly.
No MCP client, no production data. Uses a temporary workspace directory.
"""

import os
import sys
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from first_mcp.fileio import WorkspaceManager


class TestWorkspaceEditTextfile(unittest.TestCase):
    """Test edit_text_file() across all modes and error paths."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self._original_ws_path = os.environ.get('FIRST_MCP_WORKSPACE_PATH')
        os.environ['FIRST_MCP_WORKSPACE_PATH'] = self.test_dir
        self.ws = WorkspaceManager()
        # Seed a default test file
        self.ws.store_text_file("test.txt", "alpha\nbeta\ngamma\n")

    def tearDown(self):
        if self._original_ws_path is not None:
            os.environ['FIRST_MCP_WORKSPACE_PATH'] = self._original_ws_path
        else:
            os.environ.pop('FIRST_MCP_WORKSPACE_PATH', None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _read(self, filename="test.txt"):
        return self.ws.read_text_file(filename)["content"]

    # ------------------------------------------------------------------
    # Mode: append
    # ------------------------------------------------------------------

    def test_append_adds_to_end(self):
        result = self.ws.edit_text_file("test.txt", "append", "delta\n")
        self.assertTrue(result["success"])
        self.assertEqual(self._read(), "alpha\nbeta\ngamma\ndelta\n")

    def test_append_no_anchor_needed(self):
        """append should succeed even when anchor is omitted."""
        result = self.ws.edit_text_file("test.txt", "append", "x")
        self.assertNotIn("error", result)

    # ------------------------------------------------------------------
    # Mode: prepend
    # ------------------------------------------------------------------

    def test_prepend_adds_to_start(self):
        result = self.ws.edit_text_file("test.txt", "prepend", "zero\n")
        self.assertTrue(result["success"])
        self.assertTrue(self._read().startswith("zero\n"))

    # ------------------------------------------------------------------
    # Mode: insert_after
    # ------------------------------------------------------------------

    def test_insert_after_places_content_after_anchor(self):
        result = self.ws.edit_text_file("test.txt", "insert_after", " INSERTED", anchor="alpha")
        self.assertTrue(result["success"])
        content = self._read()
        self.assertIn("alpha INSERTED\n", content)

    def test_insert_after_only_modifies_first_occurrence(self):
        self.ws.store_text_file("dup.txt", "x x x", overwrite=True)
        self.ws.edit_text_file("dup.txt", "insert_after", "Y", anchor="x")
        content = self.ws.read_text_file("dup.txt")["content"]
        # Only the first 'x' should be affected
        self.assertEqual(content.count("Y"), 1)

    # ------------------------------------------------------------------
    # Mode: insert_before
    # ------------------------------------------------------------------

    def test_insert_before_places_content_before_anchor(self):
        result = self.ws.edit_text_file("test.txt", "insert_before", "BEFORE ", anchor="beta")
        self.assertTrue(result["success"])
        self.assertIn("BEFORE beta", self._read())

    # ------------------------------------------------------------------
    # Mode: replace
    # ------------------------------------------------------------------

    def test_replace_substitutes_first_occurrence(self):
        self.ws.store_text_file("r.txt", "cat cat cat", overwrite=True)
        result = self.ws.edit_text_file("r.txt", "replace", "dog", anchor="cat")
        self.assertTrue(result["success"])
        self.assertEqual(self.ws.read_text_file("r.txt")["content"], "dog cat cat")

    # ------------------------------------------------------------------
    # Mode: replace_all
    # ------------------------------------------------------------------

    def test_replace_all_substitutes_every_occurrence(self):
        self.ws.store_text_file("ra.txt", "foo bar foo baz foo", overwrite=True)
        result = self.ws.edit_text_file("ra.txt", "replace_all", "qux", anchor="foo")
        self.assertTrue(result["success"])
        self.assertEqual(result["replacements"], 3)
        self.assertEqual(self.ws.read_text_file("ra.txt")["content"], "qux bar qux baz qux")

    def test_replace_all_reports_replacement_count(self):
        self.ws.store_text_file("cnt.txt", "a a a a", overwrite=True)
        result = self.ws.edit_text_file("cnt.txt", "replace_all", "b", anchor="a")
        self.assertEqual(result["replacements"], 4)

    # ------------------------------------------------------------------
    # Metadata update
    # ------------------------------------------------------------------

    def test_edit_updates_metadata_size_and_timestamp(self):
        import time
        time.sleep(0.01)  # ensure measurable time difference
        original_meta = self.ws._load_metadata().get("test.txt", {})
        self.ws.edit_text_file("test.txt", "append", "extra content\n")
        updated_meta = self.ws._load_metadata().get("test.txt", {})
        self.assertGreater(updated_meta["size_bytes"], original_meta.get("size_bytes", 0))
        self.assertGreaterEqual(updated_meta["last_modified"], original_meta.get("last_modified", ""))

    # ------------------------------------------------------------------
    # Error paths
    # ------------------------------------------------------------------

    def test_error_file_not_found(self):
        result = self.ws.edit_text_file("nonexistent.txt", "append", "x")
        self.assertIn("error", result)

    def test_error_anchor_not_found_replace(self):
        result = self.ws.edit_text_file("test.txt", "replace", "x", anchor="ZZZNOMATCH")
        self.assertIn("error", result)

    def test_error_anchor_not_found_insert_after(self):
        result = self.ws.edit_text_file("test.txt", "insert_after", "x", anchor="ZZZNOMATCH")
        self.assertIn("error", result)

    def test_error_anchor_not_found_replace_all(self):
        result = self.ws.edit_text_file("test.txt", "replace_all", "x", anchor="ZZZNOMATCH")
        self.assertIn("error", result)

    def test_error_missing_anchor_param_for_anchor_modes(self):
        for mode in ("insert_after", "insert_before", "replace", "replace_all"):
            with self.subTest(mode=mode):
                result = self.ws.edit_text_file("test.txt", mode, "x")
                self.assertIn("error", result, f"Mode '{mode}' should require anchor")

    def test_error_invalid_mode(self):
        result = self.ws.edit_text_file("test.txt", "overwrite", "x")
        self.assertIn("error", result)

    def test_error_path_traversal_filename(self):
        result = self.ws.edit_text_file("../evil.txt", "append", "x")
        self.assertIn("error", result)

    def test_result_includes_mode_and_size(self):
        result = self.ws.edit_text_file("test.txt", "append", "xyz")
        self.assertEqual(result["mode"], "append")
        self.assertIn("size_bytes", result)
        self.assertIn("filename", result)


if __name__ == '__main__':
    print("Data Processing Layer Tests — workspace edit")
    unittest.main(verbosity=2)
