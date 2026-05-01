"""
Assistant tools — LLM-based utilities backed by Gemini.

Model is read from FIRST_MCP_ASSISTANT_MODEL (default: gemini-2.5-flash).
Requires GOOGLE_API_KEY.
"""

import os
from typing import Any, Dict

try:
    import google.genai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

ASSISTANT_MODEL = os.getenv('FIRST_MCP_ASSISTANT_MODEL', 'gemini-2.5-flash')


def get_second_opinion(question: str, context: str = "") -> Dict[str, Any]:
    """
    Send a question to Gemini and return its answer.

    Args:
        question: The question to ask.
        context:  Optional background context to include with the question.
    """
    if not GENAI_AVAILABLE:
        return {'success': False, 'error': 'google-genai not installed'}

    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return {'success': False, 'error': 'GOOGLE_API_KEY not set'}

    prompt = question if not context else f"{context}\n\n{question}"

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=ASSISTANT_MODEL,
            contents=prompt,
        )
        return {
            'success': True,
            'answer': response.text,
            'model': ASSISTANT_MODEL,
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
