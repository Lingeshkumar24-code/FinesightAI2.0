"""
Vector store abstraction.
---------------------------
Production target: Supabase pgvector (see infra/supabase/schema.sql).
For local dev + unit tests, `InMemoryVectorStore` implements the exact
same interface using cosine similarity over a bag-of-words vector, so
tests run with zero network calls and zero embedding-API cost, and the
only thing that changes when you flip to Postgres is which class you
instantiate.
"""
from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class DocumentChunk:
    id: str
    text: str
    source: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ScoredChunk:
    chunk: DocumentChunk
    score: float


_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _vectorize(text: str) -> Counter:
    return Counter(_tokenize(text))


def _cosine_similarity(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in shared)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, chunks: list[DocumentChunk]) -> None: ...

    @abstractmethod
    def similarity_search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict | None = None,
    ) -> list[ScoredChunk]: ...


class InMemoryVectorStore(VectorStore):
    """Deterministic, dependency-free "embedding" using term-frequency
    cosine similarity. This is intentionally simple — good enough for
    retrieving the right uploaded financial document/section for an MVP,
    swappable for a real embedding model + pgvector in production
    without changing any caller."""

    def __init__(self) -> None:
        self._chunks: dict[str, DocumentChunk] = {}
        self._vectors: dict[str, Counter] = {}

    def upsert(self, chunks: list[DocumentChunk]) -> None:
        for chunk in chunks:
            self._chunks[chunk.id] = chunk
            self._vectors[chunk.id] = _vectorize(chunk.text)

    def similarity_search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict | None = None,
    ) -> list[ScoredChunk]:
        query_vec = _vectorize(query)
        scored = [
            ScoredChunk(chunk=self._chunks[cid], score=_cosine_similarity(query_vec, vec))
            for cid, vec in self._vectors.items()
            if not metadata_filter
            or all(self._chunks[cid].metadata.get(key) == value for key, value in metadata_filter.items())
        ]
        scored.sort(key=lambda s: s.score, reverse=True)
        return [s for s in scored if s.score > 0][:top_k]

    def __len__(self) -> int:
        return len(self._chunks)
