import os
import requests
import zipfile
from pathlib import Path
from typing import List, Dict
from .canonical import extract_canonical_name, find_book_file, get_canonical_books, CANONICAL_NT_BOOKS, CANONICAL_OT_BOOKS

SUPPORTED_VERSIONS = {"ESV"}


def get_bible_data_dir(version: str = "ESV") -> Path:
    """Return the data directory for a given Bible version.

    Path: $FIRST_MCP_DATA_PATH/bible_data/{version}/
    """
    base = os.getenv('FIRST_MCP_DATA_PATH', '.')
    return Path(base) / "bible_data" / version


class ESVBibleDownloader:
    """Download and manage ESV Bible text from the mdbible GitHub repository."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.zip_url = "https://github.com/lguenth/mdbible/archive/refs/heads/main.zip"
        self.bible_dir = self.data_dir / "mdbible-main"

    def download_bible(self, force_redownload: bool = False) -> bool:
        """Download ESV Bible markdown files from GitHub. No-op if already present."""
        if self.bible_dir.exists() and not force_redownload:
            return True

        self.data_dir.mkdir(parents=True, exist_ok=True)

        try:
            print(f"Downloading ESV Bible from {self.zip_url}...")
            response = requests.get(self.zip_url, timeout=60)
            response.raise_for_status()

            zip_path = self.data_dir / "mdbible.zip"
            with open(zip_path, 'wb') as f:
                f.write(response.content)

            print("Extracting files...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.data_dir)

            zip_path.unlink()
            print(f"ESV Bible data ready at {self.bible_dir}")
            return True

        except Exception as e:
            print(f"Error downloading Bible data: {e}")
            return False

    def get_available_books(self) -> List[str]:
        """Get list of all books actually present in the data directory."""
        return sorted(get_canonical_books(self.bible_dir / "by_book"))

    def load_book_complete(self, canonical_book_name: str) -> str:
        """Load a complete book from the by_book directory."""
        book_file = find_book_file(canonical_book_name, self.bible_dir / "by_book")
        if not book_file:
            raise FileNotFoundError(
                f"Book file not found for '{canonical_book_name}'. "
                f"Data directory: {self.bible_dir}"
            )
        with open(book_file, 'r', encoding='utf-8') as f:
            return f.read()

    def get_new_testament_books(self) -> List[str]:
        return CANONICAL_NT_BOOKS.copy()

    def get_old_testament_books(self) -> List[str]:
        return CANONICAL_OT_BOOKS.copy()
