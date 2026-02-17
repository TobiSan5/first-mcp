"""
Canonical book reference system.

Provides canonical book names derived directly from GitHub source filenames,
enabling Path.rglob() usage and eliminating reference ambiguity at the data layer.
"""

import re
from pathlib import Path
from typing import Set, Optional


def extract_canonical_name(filename: str) -> str:
    """Extract canonical book name from GitHub source filename.

    Args:
        filename: Filename like "40_Matthew.md" or "01_Genesis.md"

    Returns:
        Canonical name like "Matthew" or "Genesis"
    """
    name = re.sub(r'^\d+_', '', filename)
    name = re.sub(r'\.md$', '', name)
    return name


def get_canonical_books(data_dir: Path) -> Set[str]:
    """Get all available canonical book names from data directory."""
    canonical_books = set()

    if data_dir.exists():
        for md_file in data_dir.glob('*.md'):
            if re.match(r'^\d+_', md_file.name):
                canonical_name = extract_canonical_name(md_file.name)
                canonical_books.add(canonical_name)

    return canonical_books


def find_book_file(canonical_name: str, data_dir: Path) -> Optional[Path]:
    """Find the file for a canonical book name using Path.rglob()."""
    pattern = f"*_{canonical_name}.md"
    matches = list(data_dir.rglob(pattern))

    if matches:
        return matches[0]
    return None


def is_canonical_name(name: str, data_dir: Path) -> bool:
    """Check if a name is a valid canonical book name."""
    return find_book_file(name, data_dir) is not None


# Standard canonical book lists (derived from actual GitHub filenames)
CANONICAL_OT_BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth", "I_Samuel", "II_Samuel", "I_Kings",
    "II_Kings", "I_Chronicles", "II_Chronicles", "Ezra", "Nehemiah",
    "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes",
    "Song_of_Solomon", "Isaiah", "Jeremiah", "Lamentations",
    "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah",
    "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai",
    "Zechariah", "Malachi"
]

CANONICAL_NT_BOOKS = [
    "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "I_Corinthians", "II_Corinthians", "Galatians",
    "Ephesians", "Philippians", "Colossians", "I_Thessalonians",
    "II_Thessalonians", "I_Timothy", "II_Timothy", "Titus", "Philemon",
    "Hebrews", "James", "I_Peter", "II_Peter", "I_John", "II_John",
    "III_John", "Jude", "Revelation"
]
