"""
Lightweight embedding backend for the retrieval pipeline.

Design note
-----------
Sentence-transformer / OpenAI embedding models require either a network
download (HuggingFace hub) or a paid API call. To keep this project runnable
offline/hackathon-fast and dependency-light, we default to a TF-IDF vector
space (scikit-learn) fit directly on the curriculum corpus. It is a genuine
vector embedding technique (sparse, but a real vector space with cosine
similarity) and is swappable: set EMBEDDING_BACKEND=sentence-transformers to
use `sentence-transformers` instead if the model is available in your
environment, without touching any calling code.

Both backends implement the same tiny interface: `fit(corpus)` and
`embed(texts) -> np.ndarray`.
"""
from __future__ import annotations

import os
from typing import Protocol

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class EmbeddingBackend(Protocol):
    def fit(self, corpus: list[str]) -> None: ...
    def embed(self, texts: list[str]) -> np.ndarray: ...


class TfidfEmbeddingBackend:
    """Default, offline-friendly embedding backend."""

    def __init__(self) -> None:
        self._vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=4096,
        )
        self._fitted = False

    def fit(self, corpus: list[str]) -> None:
        self._vectorizer.fit(corpus)
        self._fitted = True

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("EmbeddingBackend.fit() must be called before embed().")
        matrix = self._vectorizer.transform(texts)
        return matrix.toarray()


class SentenceTransformerEmbeddingBackend:
    """Optional higher-quality backend. Requires `sentence-transformers`
    and network/model-cache access. Not used by default."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer  # lazy import

        self._model = SentenceTransformer(model_name)

    def fit(self, corpus: list[str]) -> None:
        # Stateless embedding model — nothing to fit.
        return None

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._model.encode(texts, normalize_embeddings=True))


def get_embedding_backend() -> EmbeddingBackend:
    backend_name = os.getenv("EMBEDDING_BACKEND", "tfidf").lower()
    if backend_name == "sentence-transformers":
        return SentenceTransformerEmbeddingBackend()
    return TfidfEmbeddingBackend()


def cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity between one query vector and a matrix of vectors."""
    if matrix.size == 0:
        return np.array([])
    query_norm = np.linalg.norm(query_vec) + 1e-10
    matrix_norms = np.linalg.norm(matrix, axis=1) + 1e-10
    dot = matrix @ query_vec
    return dot / (matrix_norms * query_norm)
