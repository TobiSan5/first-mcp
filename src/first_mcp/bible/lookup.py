"""
Biblical reference lookup.

Supported reference formats:
    "Gen 1:1"           Single verse
    "Gen 1:1-10"        Verse range
    "Gen 1"             Entire chapter
    "Gen 1-4"           Chapter range
    "John 3:16; Rom 6:23"  Multiple references (semicolon separated)

Common abbreviations are supported for all 66 books.
"""

import re
from typing import List, Dict, Tuple, Union, Optional
from .canonical import CANONICAL_NT_BOOKS, CANONICAL_OT_BOOKS
from .books import VerseAccessor
from .sources import SUPPORTED_VERSIONS


class BibleReference:
    """A parsed biblical reference."""

    def __init__(self, book: str, start_chapter: int, end_chapter: Optional[int] = None,
                 start_verse: Optional[int] = None, end_verse: Optional[int] = None):
        self.book = book
        self.start_chapter = start_chapter
        self.end_chapter = end_chapter if end_chapter is not None else start_chapter
        self.start_verse = start_verse
        self.end_verse = end_verse if end_verse is not None else start_verse

    def __str__(self):
        if self.start_verse is None:
            if self.start_chapter == self.end_chapter:
                return f"{self.book} {self.start_chapter}"
            return f"{self.book} {self.start_chapter}-{self.end_chapter}"
        if self.start_verse == self.end_verse:
            return f"{self.book} {self.start_chapter}:{self.start_verse}"
        return f"{self.book} {self.start_chapter}:{self.start_verse}-{self.end_verse}"

    def __repr__(self):
        return f"BibleReference('{self}')"


class BibleLookup:
    """Parse and look up biblical references, with per-version accessor caching."""

    # Maps user abbreviations/aliases to canonical names
    BOOK_MAPPINGS = {
        # Old Testament
        'gen': 'Genesis', 'genesis': 'Genesis',
        'ex': 'Exodus', 'exod': 'Exodus', 'exodus': 'Exodus',
        'lev': 'Leviticus', 'leviticus': 'Leviticus',
        'num': 'Numbers', 'numbers': 'Numbers',
        'deut': 'Deuteronomy', 'dt': 'Deuteronomy', 'deuteronomy': 'Deuteronomy',
        'josh': 'Joshua', 'joshua': 'Joshua',
        'judg': 'Judges', 'judges': 'Judges',
        'ruth': 'Ruth',
        '1sam': 'I_Samuel', '1 sam': 'I_Samuel', '1 samuel': 'I_Samuel', '1samuel': 'I_Samuel',
        '2sam': 'II_Samuel', '2 sam': 'II_Samuel', '2 samuel': 'II_Samuel', '2samuel': 'II_Samuel',
        '1kgs': 'I_Kings', '1 kings': 'I_Kings', '1 kgs': 'I_Kings', '1kings': 'I_Kings',
        '2kgs': 'II_Kings', '2 kings': 'II_Kings', '2 kgs': 'II_Kings', '2kings': 'II_Kings',
        '1chr': 'I_Chronicles', '1 chronicles': 'I_Chronicles', '1 chron': 'I_Chronicles', '1chronicles': 'I_Chronicles',
        '2chr': 'II_Chronicles', '2 chronicles': 'II_Chronicles', '2 chron': 'II_Chronicles', '2chronicles': 'II_Chronicles',
        'ezra': 'Ezra',
        'neh': 'Nehemiah', 'nehemiah': 'Nehemiah',
        'esth': 'Esther', 'esther': 'Esther',
        'job': 'Job',
        'ps': 'Psalms', 'psa': 'Psalms', 'psalms': 'Psalms', 'psalm': 'Psalms',
        'prov': 'Proverbs', 'proverbs': 'Proverbs',
        'eccl': 'Ecclesiastes', 'ecclesiastes': 'Ecclesiastes', 'ecc': 'Ecclesiastes',
        'song': 'Song_of_Solomon', 'sos': 'Song_of_Solomon',
        'song of solomon': 'Song_of_Solomon', 'song of songs': 'Song_of_Solomon',
        'isa': 'Isaiah', 'isaiah': 'Isaiah',
        'jer': 'Jeremiah', 'jeremiah': 'Jeremiah',
        'lam': 'Lamentations', 'lamentations': 'Lamentations',
        'ezek': 'Ezekiel', 'ezekiel': 'Ezekiel', 'eze': 'Ezekiel',
        'dan': 'Daniel', 'daniel': 'Daniel',
        'hos': 'Hosea', 'hosea': 'Hosea',
        'joel': 'Joel',
        'amos': 'Amos',
        'obad': 'Obadiah', 'obadiah': 'Obadiah',
        'jonah': 'Jonah',
        'mic': 'Micah', 'micah': 'Micah',
        'nah': 'Nahum', 'nahum': 'Nahum',
        'hab': 'Habakkuk', 'habakkuk': 'Habakkuk',
        'zeph': 'Zephaniah', 'zephaniah': 'Zephaniah',
        'hag': 'Haggai', 'haggai': 'Haggai',
        'zech': 'Zechariah', 'zechariah': 'Zechariah',
        'mal': 'Malachi', 'malachi': 'Malachi',
        # New Testament
        'matt': 'Matthew', 'mt': 'Matthew', 'matthew': 'Matthew',
        'mark': 'Mark', 'mk': 'Mark', 'mar': 'Mark',
        'luke': 'Luke', 'lk': 'Luke', 'luk': 'Luke',
        'john': 'John', 'jn': 'John', 'joh': 'John',
        'acts': 'Acts', 'ac': 'Acts',
        'rom': 'Romans', 'romans': 'Romans',
        '1cor': 'I_Corinthians', '1 cor': 'I_Corinthians', '1 corinthians': 'I_Corinthians', '1corinthians': 'I_Corinthians',
        '2cor': 'II_Corinthians', '2 cor': 'II_Corinthians', '2 corinthians': 'II_Corinthians', '2corinthians': 'II_Corinthians',
        'gal': 'Galatians', 'galatians': 'Galatians',
        'eph': 'Ephesians', 'ephesians': 'Ephesians',
        'phil': 'Philippians', 'philippians': 'Philippians',
        'col': 'Colossians', 'colossians': 'Colossians',
        '1thess': 'I_Thessalonians', '1 thess': 'I_Thessalonians', '1 thessalonians': 'I_Thessalonians', '1thessalonians': 'I_Thessalonians',
        '2thess': 'II_Thessalonians', '2 thess': 'II_Thessalonians', '2 thessalonians': 'II_Thessalonians', '2thessalonians': 'II_Thessalonians',
        '1tim': 'I_Timothy', '1 tim': 'I_Timothy', '1 timothy': 'I_Timothy', '1timothy': 'I_Timothy',
        '2tim': 'II_Timothy', '2 tim': 'II_Timothy', '2 timothy': 'II_Timothy', '2timothy': 'II_Timothy',
        'titus': 'Titus', 'tit': 'Titus',
        'philem': 'Philemon', 'philemon': 'Philemon', 'phm': 'Philemon',
        'heb': 'Hebrews', 'hebrews': 'Hebrews',
        'jas': 'James', 'james': 'James', 'jam': 'James',
        '1pet': 'I_Peter', '1 peter': 'I_Peter', '1 pet': 'I_Peter', '1peter': 'I_Peter',
        '2pet': 'II_Peter', '2 peter': 'II_Peter', '2 pet': 'II_Peter', '2peter': 'II_Peter',
        '1john': 'I_John', '1 john': 'I_John', '1 jn': 'I_John', '1jn': 'I_John',
        '2john': 'II_John', '2 john': 'II_John', '2 jn': 'II_John', '2jn': 'II_John',
        '3john': 'III_John', '3 john': 'III_John', '3 jn': 'III_John', '3jn': 'III_John',
        'jude': 'Jude',
        'rev': 'Revelation', 'revelation': 'Revelation', 'revelations': 'Revelation',
    }

    def __init__(self):
        # Cache: version -> (nt_accessor, ot_accessor)
        self._accessors: Dict[str, Tuple[VerseAccessor, VerseAccessor]] = {}

    def _get_accessors(self, version: str) -> Tuple[VerseAccessor, VerseAccessor]:
        if version not in self._accessors:
            if version not in SUPPORTED_VERSIONS:
                supported = ", ".join(sorted(SUPPORTED_VERSIONS))
                raise ValueError(
                    f"Bible version '{version}' is not supported. "
                    f"Currently supported: {supported}"
                )
            self._accessors[version] = (
                VerseAccessor(is_new_testament=True, version=version),
                VerseAccessor(is_new_testament=False, version=version),
            )
        return self._accessors[version]

    def normalize_book_name(self, user_book_name: str) -> str:
        """Normalize a user-supplied book name to its canonical form."""
        all_canonical = set(CANONICAL_NT_BOOKS + CANONICAL_OT_BOOKS)
        # Already a canonical name (e.g. "II_Samuel" passed directly)
        if user_book_name in all_canonical:
            return user_book_name
        key = user_book_name.lower().strip()
        canonical = self.BOOK_MAPPINGS.get(key, user_book_name.title())
        if canonical in all_canonical:
            return canonical
        return user_book_name.title()

    def parse_reference(self, reference: str) -> BibleReference:
        """Parse a single biblical reference string into a BibleReference object."""
        reference = reference.strip()
        pattern = r'^(.+?)\s+(\d+)(?:-(\d+))?(?::(\d+)(?:-(\d+))?)?$'
        match = re.match(pattern, reference)
        if not match:
            raise ValueError(f"Invalid reference format: '{reference}'")

        book_part, start_ch, end_ch, start_v, end_v = match.groups()
        canonical_book = self.normalize_book_name(book_part)
        return BibleReference(
            canonical_book,
            int(start_ch),
            int(end_ch) if end_ch else None,
            int(start_v) if start_v else None,
            int(end_v) if end_v else None,
        )

    def lookup_reference(self, reference: Union[str, BibleReference],
                         version: str = "ESV") -> List[Tuple[str, str]]:
        """Look up verses for a reference, returning [(ref_string, verse_text), ...]."""
        ref = self.parse_reference(reference) if isinstance(reference, str) else reference

        nt_accessor, ot_accessor = self._get_accessors(version)

        if ref.book in CANONICAL_NT_BOOKS:
            books_collection = nt_accessor
        elif ref.book in CANONICAL_OT_BOOKS:
            books_collection = ot_accessor
        else:
            raise KeyError(f"Book '{ref.book}' not found")

        results = []
        for chapter_num in range(ref.start_chapter, ref.end_chapter + 1):
            if chapter_num not in books_collection[ref.book]:
                raise KeyError(f"Chapter {chapter_num} not found in {ref.book}")

            chapter = books_collection[ref.book][chapter_num]

            if ref.start_verse is None:
                for verse_num in sorted(chapter.keys()):
                    results.append((f"{ref.book} {chapter_num}:{verse_num}", chapter[verse_num]))
            else:
                if chapter_num == ref.start_chapter:
                    end_v = ref.end_verse or ref.start_verse
                    for verse_num in range(ref.start_verse, end_v + 1):
                        if verse_num not in chapter:
                            raise KeyError(
                                f"Verse {verse_num} not found in {ref.book} {chapter_num}"
                            )
                        results.append((f"{ref.book} {chapter_num}:{verse_num}", chapter[verse_num]))
                else:
                    for verse_num in sorted(chapter.keys()):
                        results.append((f"{ref.book} {chapter_num}:{verse_num}", chapter[verse_num]))

        return results


# Module-level lookup instance (shared, thread-safe at the accessor cache level)
_lookup = BibleLookup()


def bible_lookup(reference: str, version: str = "ESV") -> List[Tuple[str, str]]:
    """Look up biblical verses by reference string.

    Args:
        reference: Supports single verses, ranges, full chapters, chapter ranges,
                   and semicolon-separated multiple references.
                   Examples: "Gen 1:1", "John 3:16-17", "Ps 23", "Gen 1-4",
                             "Matt 5:3-12", "John 3:16; Rom 6:23"
        version:   Bible translation to use. Default "ESV". Currently only "ESV"
                   is supported (text from github.com/lguenth/mdbible).

    Returns:
        List of (reference_string, verse_text) tuples.
    """
    if ';' in reference:
        results = []
        for ref in reference.split(';'):
            ref = ref.strip()
            if ref:
                results.extend(_lookup.lookup_reference(ref, version=version))
        return results
    return _lookup.lookup_reference(reference, version=version)


def parse_reference(reference: str) -> BibleReference:
    """Parse a reference string into a BibleReference object."""
    return _lookup.parse_reference(reference)
