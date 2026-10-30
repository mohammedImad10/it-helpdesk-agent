from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fitz
import numpy as np
import yaml

from app.config import EMBEDDING_MODEL, INDEX_PATH, KB_ROOT
from app.retrieval.embeddings import EmbeddingProvider, build_embeddings
from app.retrieval.precedence import eligible


@dataclass
class Chunk:
    text: str
    metadata: dict[str, Any]
    source_path: str
    embedding: list[float] | None = None


def _front_matter(text: str) -> tuple[dict[str, Any], str]:
    match = re.search(r"---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError("Missing YAML document-control block.")
    return yaml.safe_load(match.group(1)), match.group(2)


def _sections(body: str) -> list[str]:
    parts = re.split(r"(?=^#{1,3}\s)", body, flags=re.MULTILINE)
    return [part.strip() for part in parts if part.strip()]


class KnowledgeBase:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks

    @classmethod
    def build(
        cls, source: Path = KB_ROOT, embedding_provider: EmbeddingProvider | None = None
    ) -> "KnowledgeBase":
        chunks: list[Chunk] = []
        for path in sorted(source.iterdir()):
            if path.suffix not in {".md", ".pdf"}:
                continue
            text = path.read_text(encoding="utf-8") if path.suffix == ".md" else "\n".join(
                page.get_text() for page in fitz.open(path)
            )
            metadata, body = _front_matter(text)
            for section in _sections(body):
                chunks.append(Chunk(section, metadata, str(path)))
        vectors = build_embeddings(
            embedding_provider if embedding_provider is not None else EmbeddingProvider.from_environment(),
            [chunk.text for chunk in chunks],
        )
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk.embedding = vector
        return cls(chunks)

    @classmethod
    def load_or_build(cls) -> "KnowledgeBase":
        provider = EmbeddingProvider.from_environment()
        if INDEX_PATH.exists():
            saved = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict) and saved.get("embedding_model") == EMBEDDING_MODEL:
                kb = cls([Chunk(**item) for item in saved["chunks"]])
                if provider is None or kb.has_embeddings:
                    return kb
        kb = cls.build(embedding_provider=provider)
        kb.persist()
        return kb

    def persist(self) -> None:
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        INDEX_PATH.write_text(
            json.dumps(
                {
                    "embedding_model": EMBEDDING_MODEL,
                    "chunks": [asdict(chunk) for chunk in self.chunks],
                },
                default=str,
            ),
            encoding="utf-8",
        )

    @property
    def has_embeddings(self) -> bool:
        return bool(self.chunks) and all(chunk.embedding is not None for chunk in self.chunks)

    def _query_embedding(self, query: str) -> list[float] | None:
        provider = EmbeddingProvider.from_environment()
        if provider is None or not self.has_embeddings:
            return None
        return provider.embed([query])[0]

    def search(self, query: str, department: str | None = None, limit: int = 5) -> list[Chunk]:
        terms = set(re.findall(r"[a-z0-9-]+", query.lower()))
        error_codes = set(re.findall(r"\b[A-Z]{2,4}-\d{2,4}\b", query.upper()))
        candidates = eligible([asdict(chunk) for chunk in self.chunks], department)
        query_embedding = self._query_embedding(query)
        query_norm = np.linalg.norm(query_embedding) if query_embedding is not None else 0.0

        def score(item: dict[str, Any]) -> tuple[int, float, int, str]:
            chunk = item["text"].lower()
            meta = item["metadata"]
            exact = len(error_codes.intersection(set(meta.get("error_codes") or [])))
            words = sum(term in chunk for term in terms if len(term) > 2)
            vector = item.get("embedding")
            semantic = 0.0
            if query_embedding is not None and vector is not None and query_norm:
                vector_array = np.asarray(vector, dtype=float)
                denominator = np.linalg.norm(vector_array) * query_norm
                semantic = float(np.dot(vector_array, query_embedding) / denominator) if denominator else 0.0
            return exact, semantic, words, str(meta["id"])

        matching = [item for item in candidates if score(item)[:3] != (0, 0.0, 0)]
        return [Chunk(**item) for item in sorted(matching, key=score, reverse=True)[:limit]]

    def by_id(self, doc_id: str) -> Chunk | None:
        return next((chunk for chunk in self.chunks if chunk.metadata["id"] == doc_id), None)
