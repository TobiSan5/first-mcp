#!/usr/bin/env python3
"""
Data Processing Layer Tests — bible module

Tests pure parsing and lookup logic with no network calls.
Covers: markdown parsing, reference parsing, book name normalisation,
version validation, and multi-reference splitting.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from first_mcp.bible.books import _parse_verse_reference, parse_chapter_markdown
from first_mcp.bible.lookup import BibleLookup, BibleReference
from first_mcp.bible.canonical import CANONICAL_NT_BOOKS, CANONICAL_OT_BOOKS
from first_mcp.bible.sources import SUPPORTED_VERSIONS

SAMPLE_MARKDOWN = """\
# John

## Chapter 3

1. There was a man of the Pharisees named Nicodemus.
2. This man came to Jesus by night.
3. Jesus answered him.

## Chapter 4

1. Now when Jesus learned that the Pharisees had heard.
2. He left Judea.
"""


class TestParseVerseReference(unittest.TestCase):
    """Test the low-level markdown line parser."""

    def test_numbered_list_format(self):
        verse_num, text = _parse_verse_reference("16. For God so loved the world")
        self.assertEqual(verse_num, 16)
        self.assertEqual(text, "For God so loved the world")

    def test_plain_number_format(self):
        verse_num, text = _parse_verse_reference("1 In the beginning")
        self.assertEqual(verse_num, 1)
        self.assertEqual(text, "In the beginning")

    def test_non_verse_line_returns_none(self):
        verse_num, _ = _parse_verse_reference("## Chapter 3")
        self.assertIsNone(verse_num)

    def test_empty_line_returns_none(self):
        verse_num, _ = _parse_verse_reference("")
        self.assertIsNone(verse_num)

    def test_leading_whitespace_stripped(self):
        verse_num, text = _parse_verse_reference("   5. Some verse text")
        self.assertEqual(verse_num, 5)
        self.assertEqual(text, "Some verse text")


class TestParseChapterMarkdown(unittest.TestCase):
    """Test full markdown → verse tuple parsing."""

    def setUp(self):
        self.verses = parse_chapter_markdown(SAMPLE_MARKDOWN, "John")

    def test_returns_list_of_tuples(self):
        self.assertIsInstance(self.verses, list)
        self.assertTrue(all(len(v) == 4 for v in self.verses))

    def test_book_name_preserved(self):
        for book, _, _, _ in self.verses:
            self.assertEqual(book, "John")

    def test_chapter_numbers_correct(self):
        chapters = {ch for _, ch, _, _ in self.verses}
        self.assertEqual(chapters, {3, 4})

    def test_verse_numbers_correct(self):
        ch3_verses = [v for _, ch, v, _ in self.verses if ch == 3]
        self.assertEqual(ch3_verses, [1, 2, 3])
        ch4_verses = [v for _, ch, v, _ in self.verses if ch == 4]
        self.assertEqual(ch4_verses, [1, 2])

    def test_verse_text_content(self):
        ch3_v1 = next(t for _, ch, v, t in self.verses if ch == 3 and v == 1)
        self.assertIn("Nicodemus", ch3_v1)

    def test_headers_not_included_as_verses(self):
        texts = [t for _, _, _, t in self.verses]
        for text in texts:
            self.assertFalse(text.startswith('#'))


class TestBibleLookupParseReference(unittest.TestCase):
    """Test BibleLookup.parse_reference() for all supported formats."""

    def setUp(self):
        self.lookup = BibleLookup()

    def test_single_verse(self):
        ref = self.lookup.parse_reference("John 3:16")
        self.assertEqual(ref.book, "John")
        self.assertEqual(ref.start_chapter, 3)
        self.assertEqual(ref.start_verse, 16)
        self.assertEqual(ref.end_verse, 16)

    def test_verse_range(self):
        ref = self.lookup.parse_reference("Gen 1:1-3")
        self.assertEqual(ref.book, "Genesis")
        self.assertEqual(ref.start_verse, 1)
        self.assertEqual(ref.end_verse, 3)

    def test_full_chapter(self):
        ref = self.lookup.parse_reference("Ps 23")
        self.assertEqual(ref.book, "Psalms")
        self.assertEqual(ref.start_chapter, 23)
        self.assertIsNone(ref.start_verse)

    def test_chapter_range(self):
        ref = self.lookup.parse_reference("Gen 1-4")
        self.assertEqual(ref.book, "Genesis")
        self.assertEqual(ref.start_chapter, 1)
        self.assertEqual(ref.end_chapter, 4)
        self.assertIsNone(ref.start_verse)

    def test_invalid_format_raises(self):
        with self.assertRaises(ValueError):
            self.lookup.parse_reference("not a reference")

    def test_str_representation_single_verse(self):
        ref = self.lookup.parse_reference("John 3:16")
        self.assertEqual(str(ref), "John 3:16")

    def test_str_representation_chapter(self):
        ref = self.lookup.parse_reference("Ps 23")
        self.assertEqual(str(ref), "Psalms 23")


class TestBookNameNormalization(unittest.TestCase):
    """Test that abbreviations map to canonical book names."""

    def setUp(self):
        self.lookup = BibleLookup()

    def _normalize(self, name):
        return self.lookup.normalize_book_name(name)

    def test_ot_abbreviations(self):
        cases = {
            "Gen": "Genesis", "gen": "Genesis",
            "Ex": "Exodus", "Ps": "Psalms", "Psa": "Psalms",
            "Isa": "Isaiah", "Jer": "Jeremiah",
            "1Sam": "I_Samuel", "2Sam": "II_Samuel",
            "1Kgs": "I_Kings", "2Kgs": "II_Kings",
        }
        for alias, expected in cases.items():
            with self.subTest(alias=alias):
                self.assertEqual(self._normalize(alias), expected)

    def test_nt_abbreviations(self):
        cases = {
            "Matt": "Matthew", "Mk": "Mark", "Lk": "Luke",
            "Jn": "John", "Rom": "Romans",
            "1Cor": "I_Corinthians", "2Cor": "II_Corinthians",
            "Rev": "Revelation", "Gal": "Galatians",
            "1Pet": "I_Peter", "2Pet": "II_Peter",
        }
        for alias, expected in cases.items():
            with self.subTest(alias=alias):
                self.assertEqual(self._normalize(alias), expected)

    def test_full_names_accepted(self):
        self.assertEqual(self._normalize("Genesis"), "Genesis")
        self.assertEqual(self._normalize("Revelation"), "Revelation")

    def test_case_insensitive(self):
        self.assertEqual(self._normalize("JOHN"), self._normalize("john"))
        self.assertEqual(self._normalize("GENESIS"), self._normalize("genesis"))

    def test_all_canonical_ot_books_present(self):
        """Every canonical OT book name should round-trip through normalization."""
        for book in CANONICAL_OT_BOOKS:
            result = self._normalize(book)
            self.assertEqual(result, book, f"{book} did not normalise correctly")

    def test_all_canonical_nt_books_present(self):
        """Every canonical NT book name should round-trip through normalization."""
        for book in CANONICAL_NT_BOOKS:
            result = self._normalize(book)
            self.assertEqual(result, book, f"{book} did not normalise correctly")


class TestVersionValidation(unittest.TestCase):
    """Test version gate in BibleLookup."""

    def setUp(self):
        self.lookup = BibleLookup()

    def test_esv_is_supported(self):
        self.assertIn("ESV", SUPPORTED_VERSIONS)

    def test_unsupported_version_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            self.lookup._get_accessors("NIV")
        self.assertIn("NIV", str(ctx.exception))
        self.assertIn("ESV", str(ctx.exception))

    def test_unsupported_version_error_message_lists_supported(self):
        try:
            self.lookup._get_accessors("KJV")
        except ValueError as e:
            self.assertIn("ESV", str(e))


class TestMultiReferenceHandling(unittest.TestCase):
    """Test semicolon-separated multi-reference parsing (no network needed)."""

    def setUp(self):
        self.lookup = BibleLookup()

    def test_parse_each_part(self):
        """Each semicolon-separated part should parse independently."""
        parts = ["John 3:16", "Rom 6:23", "Eph 2:8"]
        for part in parts:
            ref = self.lookup.parse_reference(part.strip())
            self.assertIsInstance(ref, BibleReference)

    def test_invalid_part_raises(self):
        with self.assertRaises(ValueError):
            self.lookup.parse_reference("not valid")


if __name__ == '__main__':
    print("Data Processing Layer Tests — bible module")
    unittest.main(verbosity=2)
