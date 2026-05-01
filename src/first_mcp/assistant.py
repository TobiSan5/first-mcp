"""
Assistant tools — LLM-based utilities backed by Gemini.

Model is read from FIRST_MCP_ASSISTANT_MODEL (default: gemini-2.5-flash).
Requires GOOGLE_API_KEY.
"""

import os
import pathlib
from typing import Any, Dict

ASSISTANT_MODEL = os.getenv('FIRST_MCP_ASSISTANT_MODEL', 'gemini-2.5-flash')

_PROMPTS_DIR = pathlib.Path(__file__).parent / 'prompts'


def get_second_opinion(question: str, context: str = "") -> Dict[str, Any]:
    """
    Send a question to Gemini and return its answer.

    Args:
        question: The question to ask.
        context:  Optional background context to include with the question.
    """
    import importlib
    try:
        genai = importlib.import_module('google.genai')
        genai_types = importlib.import_module('google.genai.types')
    except ImportError:
        return {'success': False, 'error': 'google-genai not installed'}

    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return {'success': False, 'error': 'GOOGLE_API_KEY not set'}

    system_prompt = (_PROMPTS_DIR / 'second_opinion.md').read_text(encoding='utf-8')
    contents = question if not context else f"{context}\n\n{question}"

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=ASSISTANT_MODEL,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
        )
        return {
            'success': True,
            'answer': response.text,
            'model': ASSISTANT_MODEL,
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
