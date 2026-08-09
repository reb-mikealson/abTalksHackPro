"""
Lightweight RAG pipeline over the curriculum.

Each curriculum "day" is flattened into a retrievable document (title +
objectives + tools). A query — e.g. a candidate's previous answer, or a
topic name — is embedded and matched against the curriculum corpus with
cosine similarity, so question generation is always *grounded* in the real
curriculum content rather than invented from scratch.

This intentionally avoids hard-coding which day maps to which question:
callers ask the index a natural-language question and get back the most
relevant curriculum chunks, at run time.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from backend.config import get_settings
from backend.models.embeddings import get_embedding_backend, cosine_similarity


@dataclass
class CurriculumChunk:
    day: int
    title: str
    type: str
    tools: list[str]
    objectives: list[str]
    module: str | None = None
    text: str = field(default="")

    def to_context_string(self) -> str:
        obj_bullets = "\n".join(f"- {o}" for o in self.objectives)
        return (
            f"Day {self.day}: {self.title} (type: {self.type})\n"
            f"Tools: {', '.join(self.tools)}\n"
            f"Objectives:\n{obj_bullets}"
        )


class CurriculumRetriever:
    """A minimal in-memory vector store over curriculum days."""

    def __init__(self, curriculum_path: Path | None = None) -> None:
        settings = get_settings()
        self._path = curriculum_path or settings.CURRICULUM_PATH
        self._chunks: list[CurriculumChunk] = []
        self._embeddings: np.ndarray | None = None
        self._backend = get_embedding_backend()
        self._load()

    # -- loading -------------------------------------------------------
    def _load(self) -> None:
        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)

        module_by_day: dict[int, str] = {}
        for module in data.get("modules", []):
            start, end = module["days"]
            for d in range(start, end + 1):
                module_by_day[d] = module["title"]

        chunks: list[CurriculumChunk] = []
        for day in data.get("days", []):
            chunk = CurriculumChunk(
                day=day["day"],
                title=day["title"],
                type=day.get("type", "BUILD"),
                tools=day.get("tools", []),
                objectives=day.get("objectives", []),
                module=module_by_day.get(day["day"]),
            )
            chunk.text = chunk.to_context_string()
            chunks.append(chunk)

        self._chunks = chunks
        corpus = [c.text for c in chunks]
        self._backend.fit(corpus)
        self._embeddings = self._backend.embed(corpus)

    # -- public API ------------------------------------------------------
    @property
    def all_days(self) -> list[CurriculumChunk]:
        return list(self._chunks)

    def get_day(self, day_number: int) -> CurriculumChunk | None:
        for c in self._chunks:
            if c.day == day_number:
                return c
        return None

    def search(self, query: str, top_k: int = 3, exclude_days: set[int] | None = None) -> list[CurriculumChunk]:
        """Semantic search over curriculum chunks for a free-text query."""
        exclude_days = exclude_days or set()
        if self._embeddings is None or not len(self._chunks):
            return []

        query_vec = self._backend.embed([query])[0]
        sims = cosine_similarity(query_vec, self._embeddings)

        scored = [
            (score, chunk)
            for score, chunk in zip(sims, self._chunks)
            if chunk.day not in exclude_days
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    def search_by_days(self, days: list[int]) -> list[CurriculumChunk]:
        wanted = set(days)
        return [c for c in self._chunks if c.day in wanted]


_retriever_singleton: CurriculumRetriever | None = None


def get_retriever() -> CurriculumRetriever:
    global _retriever_singleton
    if _retriever_singleton is None:
        _retriever_singleton = CurriculumRetriever()
    return _retriever_singleton
