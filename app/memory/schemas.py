from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class QueryType(StrEnum):
    actors = "actors"
    locations = "locations"
    items = "items"
    conflict = "conflict"
    time_ref = "time_ref"
    keywords = "keywords"


@dataclass
class QueryItem:
    type: QueryType
    q: str


@dataclass
class QueryPlan:
    queries: list[QueryItem]


@dataclass
class RecallItem:
    chunk_id: str
    chunk_text: str
    score: float
    turn_index: int
    importance: float


@dataclass
class RetrievalDebug:
    vector_hits: int
    timeline_hits: int


@dataclass
class RetrievalResult:
    canon_facts: list[dict[str, str]]
    recalls: list[RecallItem]
    open_threads: list[dict[str, str]]
    debug: RetrievalDebug


class EmbeddingProvider(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbeddingProvider:
    def __init__(self, dim: int = 768):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            seed = hashlib.sha256(text.encode("utf-8")).digest()
            values: list[float] = []
            for i in range(self.dim):
                b = seed[i % len(seed)]
                values.append((b / 255.0) * 2 - 1)
            vectors.append(values)
        return vectors


class LocalEmbeddingProvider:
    def __init__(self, dim: int = 768):
        self.dim = dim
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
            self.dim = int(self._model.get_sentence_embedding_dimension())
        except Exception:
            self._model = None
            self._fallback = FakeEmbeddingProvider(dim=dim)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            return self._fallback.embed(texts)
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, row)) for row in embeddings]


def get_embedding_provider(name: str, dim: int = 768) -> EmbeddingProvider:
    if name == "local":
        return LocalEmbeddingProvider(dim=dim)
    return FakeEmbeddingProvider(dim=dim)
