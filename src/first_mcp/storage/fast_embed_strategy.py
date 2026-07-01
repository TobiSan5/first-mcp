"""
fastembed implementation of EmbeddingStrategy.

Uses BAAI/bge-small-en-v1.5 (384-dim, ONNX) for local, GPU-optional embeddings.
The model is downloaded once by fastembed and cached under ~/.cache/fastembed/.
Import cost is deferred: fastembed is not loaded until the first embed() call.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from fastembed import TextEmbedding

_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_DIMENSIONS = 384


class FastEmbedStrategy:
    """
    EmbeddingStrategy using fastembed (BAAI/bge-small-en-v1.5, 384-dim, ONNX).

    Thread-safe: fastembed's TextEmbedding is stateless after loading; concurrent
    embed() calls are safe because each iterates an independent generator.
    """

    def __init__(self) -> None:
        self._model: TextEmbedding | None = None

    def _get_model(self) -> TextEmbedding:
        if self._model is None:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=_MODEL_NAME)
        return self._model

    @property
    def model_name(self) -> str:
        return _MODEL_NAME

    @property
    def dimensions(self) -> int:
        return _DIMENSIONS

    def embed(self, texts: list[str]) -> list[np.ndarray | None]:
        """
        Embed a batch of texts. Returns one float32 ndarray per text.
        Empty strings embed to None (the model produces near-zero vectors for
        empty input which are meaningless for similarity search).
        """
        if not texts:
            return []
        model = self._get_model()
        results: list[np.ndarray | None] = []
        for text, vec in zip(texts, model.embed(texts)):
            if not text.strip():
                results.append(None)
            else:
                results.append(np.array(vec, dtype=np.float32))
        return results
