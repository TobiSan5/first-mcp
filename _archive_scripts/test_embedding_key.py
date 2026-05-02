"""
Diagnostic: verify the current GOOGLE_API_KEY can generate embeddings.

Run from the project root:
    python _archive_scripts/test_embedding_key.py

Works with google-genai 1.x and 2.x.
"""

import os
import sys
import time


def main() -> None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("FAIL  GOOGLE_API_KEY is not set.")
        sys.exit(1)
    print(f"OK    GOOGLE_API_KEY is set ({len(api_key)} chars, ends …{api_key[-4:]})")

    try:
        import google.genai as genai
    except ImportError:
        print("FAIL  google-genai package is not installed.")
        sys.exit(1)

    import google.genai as genai  # noqa: F811 — already imported above
    print(f"OK    google-genai imported (version: {getattr(genai, '__version__', 'unknown')})")

    model = "gemini-embedding-001"
    test_text = "first-mcp embedding diagnostic test"

    print(f"\nTesting single embedding  model={model!r}  text={test_text!r}")
    t0 = time.monotonic()
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.embed_content(model=model, contents=test_text)
        elapsed = time.monotonic() - t0
        values = response.embeddings[0].values
        print(f"OK    {len(values)}-dim vector in {elapsed:.2f}s")
        print(f"      first 5 values: {[round(v, 6) for v in values[:5]]}")
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"FAIL  after {elapsed:.2f}s — {type(e).__name__}: {e}")
        sys.exit(1)

    print(f"\nTesting batch embedding  (2 texts)")
    t1 = time.monotonic()
    try:
        batch_texts = ["hello world", "memory system test"]
        response = client.models.embed_content(model=model, contents=batch_texts)
        elapsed = time.monotonic() - t1
        dims = [len(e.values) for e in response.embeddings]
        print(f"OK    {len(dims)} embeddings {dims} in {elapsed:.2f}s")
    except Exception as e:
        elapsed = time.monotonic() - t1
        print(f"FAIL  after {elapsed:.2f}s — {type(e).__name__}: {e}")
        sys.exit(1)

    print("\nAll checks passed — embeddings are working with this API key.")


if __name__ == "__main__":
    main()
