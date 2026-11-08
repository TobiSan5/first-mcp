"""
Optional server-side tag suggesters (TagSuggester implementations).

The v2 memory system does not need an LLM: clients suggest tags, and the
tagging engine maps them onto existing vocabulary with local fastembed
embeddings. A suggester is an opt-in extra, selected with the
FIRST_MCP_TAG_SUGGESTER environment variable:

    (unset) / none   — no server-side suggestions (default)
    gemini           — Google Gemini; needs GOOGLE_API_KEY and the
                       'gemini' extra (pip install first-mcp[gemini])

New vendors (OpenAI-compatible endpoints, local models via Ollama, ...) are
added here as further TagSuggester implementations; nothing else changes.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import pathlib
import sys

from .protocols import TagSuggester

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"


def _log(msg: str) -> None:
    # stderr only: stdout is the MCP stdio transport.
    print(f"[first-mcp] {msg}", file=sys.stderr, flush=True)


class GeminiTagSuggester:
    """Tag candidates from Google Gemini using structured JSON output."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._api_key = api_key
        self._model = model
        self._client = None  # google.genai.Client, lazy

    @property
    def name(self) -> str:
        return f"gemini:{self._model}"

    def suggest(self, content: str) -> list[str]:
        from pydantic import BaseModel

        genai_types = importlib.import_module("google.genai.types")

        class _TagList(BaseModel):
            tags: list[str]

        prompt_template = (_PROMPTS_DIR / "tag_generation.md").read_text(encoding="utf-8")
        prompt = prompt_template.format(content=content[:600])

        response = self._get_client().models.generate_content(
            model=self._model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_TagList,
            ),
        )
        return list(_TagList.model_validate_json(response.text).tags)

    def _get_client(self):
        if self._client is None:
            genai = importlib.import_module("google.genai")
            self._client = genai.Client(api_key=self._api_key)
        return self._client


def get_tag_suggester_from_env() -> TagSuggester | None:
    """
    Build the configured suggester, or None when disabled or misconfigured.

    Misconfiguration never raises: the server keeps working on client-supplied
    tags and the problem is reported on stderr.
    """
    choice = os.getenv("FIRST_MCP_TAG_SUGGESTER", "none").strip().lower()

    if choice in ("", "none", "off"):
        return None

    if choice == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            _log("FIRST_MCP_TAG_SUGGESTER=gemini but GOOGLE_API_KEY is not set; "
                 "continuing without a tag suggester.")
            return None
        if importlib.util.find_spec("google.genai") is None:
            _log("FIRST_MCP_TAG_SUGGESTER=gemini but google-genai is not installed "
                 "(pip install first-mcp[gemini]); continuing without a tag suggester.")
            return None
        model = os.getenv("FIRST_MCP_TAGGING_MODEL", "gemini-2.5-flash")
        return GeminiTagSuggester(api_key=api_key, model=model)

    _log(f"Unknown FIRST_MCP_TAG_SUGGESTER={choice!r}; continuing without a tag suggester.")
    return None
