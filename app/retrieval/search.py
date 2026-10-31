from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import chromadb
import fitz
import yaml
from chromadb.config import Settings
from chromadb.errors import InvalidCollectionException

from app.config import EMBEDDING_MODEL, KB_ROOT, VECTOR_DB_PATH
from app.retrieval.embeddings import EmbeddingProvider, build_embeddings
from app.retrieval.precedence import eligible, precedence_key

COLLECTION_NAME = "helpdesk_kb"
CHROMA_SETTINGS = Settings(anonymized_telemetry=False)


@dataclass
class Chunk:
    text: str
    metadata: dict[str, Any]
    source_path: str
    embedding: list[float] | None = None
    vector_id: str | None = None


def _front_matter(text: str) -> tuple[dict[str, Any], str]:
    match = re.search(r"---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError("Missing YAML document-control block.")
    return yaml.safe_load(match.group(1)), match.group(2)


def _sections(body: str) -> list[str]:
    parts = re.split(r"(?=^#{1,3}\s)", body, flags=re.MULTILINE)
    return [part.strip() for part in parts if part.strip()]


class KnowledgeBase:
    def __init__(self, chunks: list[Chunk], collection: Any | None = None, client: Any | None = None) -> None:
        self.chunks = chunks
        self._client = client
        self.collection = collection
        for index, chunk in enumerate(self.chunks):
            chunk.vector_id = chunk.vector_id or f"{chunk.metadata['id']}-{index}"
        if self.collection is None:
            self._client = chromadb.EphemeralClient(settings=CHROMA_SETTINGS)
            self.collection = self._create_collection(
                self._client,
                self.has_embeddings,
                f"{COLLECTION_NAME}_{uuid.uuid4().hex}",
            )
            self._write_chunks()

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
        client = chromadb.PersistentClient(path=str(VECTOR_DB_PATH), settings=CHROMA_SETTINGS)
        try:
            collection = client.get_collection(COLLECTION_NAME)
            stored_model = (collection.metadata or {}).get("embedding_model")
            stored_embeddings = bool((collection.metadata or {}).get("has_embeddings"))
            if stored_model == EMBEDDING_MODEL and (provider is None or stored_embeddings):
                return cls._from_collection(collection, client, stored_embeddings)
        except (ValueError, InvalidCollectionException):
            pass

        kb = cls.build(embedding_provider=provider)
        kb.persist()
        return kb

    @classmethod
    def _from_collection(cls, collection: Any, client: Any, has_embeddings: bool) -> "KnowledgeBase":
        stored = collection.get(include=["documents", "metadatas", "embeddings"])
        chunks = [
            Chunk(
                text=str(document),
                metadata=json.loads(metadata["metadata_json"]),
                source_path=str(metadata["source_path"]),
                embedding=list(embedding) if has_embeddings else None,
                vector_id=str(vector_id),
            )
            for vector_id, document, metadata, embedding in zip(
                stored["ids"],
                stored["documents"],
                stored["metadatas"],
                stored["embeddings"],
                strict=True,
            )
        ]
        return cls(chunks, collection=collection, client=client)

    @property
    def has_embeddings(self) -> bool:
        return bool(self.chunks) and all(chunk.embedding is not None for chunk in self.chunks)

    def _create_collection(self, client: Any, has_embeddings: bool, name: str = COLLECTION_NAME) -> Any:
        return client.create_collection(
            name,
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": EMBEDDING_MODEL,
                "has_embeddings": has_embeddings,
            },
            embedding_function=None,
        )

    def _write_chunks(self) -> None:
        if not self.chunks:
            return
        self.collection.upsert(
            ids=[str(chunk.vector_id) for chunk in self.chunks],
            documents=[chunk.text for chunk in self.chunks],
            embeddings=[chunk.embedding or [0.0] for chunk in self.chunks],
            metadatas=[
                {
                    "metadata_json": json.dumps(chunk.metadata, default=str, sort_keys=True),
                    "source_path": chunk.source_path,
                }
                for chunk in self.chunks
            ],
        )

    def persist(self) -> None:
        VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(VECTOR_DB_PATH), settings=CHROMA_SETTINGS)
        try:
            client.delete_collection(COLLECTION_NAME)
        except (ValueError, InvalidCollectionException):
            pass
        self._client = client
        self.collection = self._create_collection(client, self.has_embeddings)
        self._write_chunks()

    def _query_embedding(self, query: str) -> list[float] | None:
        provider = EmbeddingProvider.from_environment()
        if provider is None or not self.has_embeddings:
            return None
        return provider.embed([query])[0]

    def _semantic_scores(self, query_embedding: list[float] | None, limit: int) -> dict[str, float]:
        if query_embedding is None or not self.collection.count():
            return {}
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(self.collection.count(), max(limit * 10, 25)),
            include=["distances"],
        )
        return {
            str(vector_id): 1.0 - float(distance)
            for vector_id, distance in zip(result["ids"][0], result["distances"][0], strict=True)
        }

    def search(self, query: str, department: str | None = None, limit: int = 5) -> list[Chunk]:
        terms = set(re.findall(r"[a-z0-9-]+", query.lower()))
        error_codes = set(re.findall(r"\b[A-Z]{2,4}-\d{2,4}\b", query.upper()))
        candidates = eligible([asdict(chunk) for chunk in self.chunks], department)
        semantic_scores = self._semantic_scores(self._query_embedding(query), limit)

        def score(item: dict[str, Any]) -> tuple[int, float, int]:
            chunk = item["text"].lower()
            meta = item["metadata"]
            exact = len(error_codes.intersection(set(meta.get("error_codes") or [])))
            words = sum(term in chunk for term in terms if len(term) > 2)
            semantic = semantic_scores.get(str(item["vector_id"]), 0.0)
            return exact, semantic, words

        matching = [item for item in candidates if score(item) != (0, 0.0, 0)]
        best_by_document: dict[str, dict[str, Any]] = {}
        for item in matching:
            document_id = str(item["metadata"]["id"])
            existing = best_by_document.get(document_id)
            if existing is None or score(item) > score(existing):
                best_by_document[document_id] = item

        def rank(item: dict[str, Any]) -> tuple[Any, ...]:
            exact, semantic, words = score(item)
            precedence = precedence_key(item, department)
            if exact:
                return (
                    -exact,
                    precedence,
                    -semantic,
                    -words,
                    str(item["vector_id"]),
                )
            return (
                0,
                -semantic,
                -words,
                precedence,
                str(item["vector_id"]),
            )

        return [Chunk(**item) for item in sorted(best_by_document.values(), key=rank)[:limit]]

    def by_id(self, doc_id: str) -> Chunk | None:
        return next((chunk for chunk in self.chunks if chunk.metadata["id"] == doc_id), None)
