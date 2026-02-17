"""
Verse accessor classes for direct biblical text access.

Usage:
    accessor = VerseAccessor(is_new_testament=True, version="ESV")
    text = accessor["John"][3][16]
"""

import re
from typing import Dict, Optional
from .sources import ESVBibleDownloader, get_bible_data_dir
from .canonical import CANONICAL_NT_BOOKS, CANONICAL_OT_BOOKS


# ---------------------------------------------------------------------------
# Markdown parsing (extracted from pynt extraction layer, no spaCy required)
# ---------------------------------------------------------------------------

def _parse_verse_reference(line: str):
    """Extract (verse_number, verse_text) from a markdown line, or (None, line)."""
    match = re.match(r'^(\d+)\.\s+(.+)$', line.strip())
    if match:
        return int(match.group(1)), match.group(2)
    match = re.match(r'^(\d+)\s+(.+)$', line.strip())
    if match:
        return int(match.group(1)), match.group(2)
    return None, line.strip()


def parse_chapter_markdown(markdown_text: str, book_name: str):
    """Parse a complete-book markdown file into (book, chapter, verse, text) tuples.

    Recognises:
        # Book Name          — book header, skipped
        ## Chapter N         — chapter header
        N. verse text        — verse (markdown list format)
    """
    verses = []
    current_chapter = 1

    for raw_line in markdown_text.strip().split('\n'):
        line = raw_line.strip()
        if not line:
            continue

        # Chapter header: ## Chapter 3  or  ## 3
        chapter_match = re.match(r'^##\s+.*?(\d+)', line)
        if chapter_match:
            current_chapter = int(chapter_match.group(1))
            continue

        # Book header: # Genesis
        if line.startswith('#') and not line.startswith('##'):
            continue

        verse_num, verse_text = _parse_verse_reference(line)
        if verse_num and verse_text:
            verses.append((book_name, current_chapter, verse_num, verse_text))

    return verses


# ---------------------------------------------------------------------------
# Accessor classes
# ---------------------------------------------------------------------------

class VerseAccessor:
    """Dictionary-style access to biblical verses for a specific version."""

    def __init__(self, is_new_testament: bool = True, version: str = "ESV"):
        self.is_new_testament = is_new_testament
        self.version = version
        self._downloader: Optional[ESVBibleDownloader] = None
        self._parsed_books: Dict[str, Dict[int, Dict[int, str]]] = {}
        self._book_names = (
            CANONICAL_NT_BOOKS.copy() if is_new_testament else CANONICAL_OT_BOOKS.copy()
        )

    def _get_downloader(self) -> ESVBibleDownloader:
        if self._downloader is None:
            self._downloader = ESVBibleDownloader(get_bible_data_dir(self.version))
        return self._downloader

    def _load_book_data(self, canonical_book_name: str) -> Dict[int, Dict[int, str]]:
        """Load and parse a book into {chapter: {verse: text}} structure."""
        if canonical_book_name in self._parsed_books:
            return self._parsed_books[canonical_book_name]

        downloader = self._get_downloader()

        if not downloader.download_bible():
            raise RuntimeError("Failed to download Bible data")

        book_markdown = downloader.load_book_complete(canonical_book_name)
        raw_verses = parse_chapter_markdown(book_markdown, canonical_book_name)

        chapters: Dict[int, Dict[int, str]] = {}
        for _, chapter, verse, text in raw_verses:
            chapters.setdefault(chapter, {})[verse] = text

        self._parsed_books[canonical_book_name] = chapters
        return chapters

    def __getitem__(self, book_name: str) -> 'ChapterAccessor':
        if book_name not in self._book_names:
            testament = "New Testament" if self.is_new_testament else "Old Testament"
            raise KeyError(f"Book '{book_name}' not found in {testament}")
        return ChapterAccessor(self, book_name)

    def __contains__(self, book_name: str) -> bool:
        return book_name in self._book_names

    def __iter__(self):
        return iter(self._book_names)

    def keys(self):
        return self._book_names


class ChapterAccessor:
    """Access chapters within a book."""

    def __init__(self, verse_accessor: VerseAccessor, book_name: str):
        self._va = verse_accessor
        self.book_name = book_name
        self._chapters: Optional[Dict[int, Dict[int, str]]] = None

    def _get_chapters(self) -> Dict[int, Dict[int, str]]:
        if self._chapters is None:
            self._chapters = self._va._load_book_data(self.book_name)
        return self._chapters

    def __getitem__(self, chapter_num: int) -> 'VerseChapterAccessor':
        chapters = self._get_chapters()
        if chapter_num not in chapters:
            raise KeyError(f"Chapter {chapter_num} not found in {self.book_name}")
        return VerseChapterAccessor(chapters[chapter_num])

    def __contains__(self, chapter_num: int) -> bool:
        return chapter_num in self._get_chapters()

    def __iter__(self):
        return iter(sorted(self._get_chapters().keys()))

    def keys(self):
        return sorted(self._get_chapters().keys())


class VerseChapterAccessor:
    """Access individual verses within a chapter."""

    def __init__(self, verses: Dict[int, str]):
        self.verses = verses

    def __getitem__(self, verse_num: int) -> str:
        if verse_num not in self.verses:
            raise KeyError(f"Verse {verse_num} not found in chapter")
        return self.verses[verse_num]

    def __contains__(self, verse_num: int) -> bool:
        return verse_num in self.verses

    def __iter__(self):
        return iter(sorted(self.verses.keys()))

    def keys(self):
        return sorted(self.verses.keys())

    def items(self):
        return [(v, self.verses[v]) for v in self.keys()]
