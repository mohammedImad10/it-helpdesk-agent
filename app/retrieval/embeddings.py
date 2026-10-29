from __future__ import annotations

import logging
from collections.abc import Sequence

from openai import OpenAI

from app.config import EMBEDDING_MODEL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """OpenRouter embedding boundary used by ingestion and semantic retrieval."""

    def __init__(self, client: OpenAI, model: str) -> None:
        self.client = client
        self.model = model

    @classmethod
    def from_environment(cls) -> "EmbeddingProvider | None":
        if not OPENROUTER_API_KEY:
            return None
        return cls(
            OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL),
            EMBEDDING_MODEL,
        )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(model=self.model, input=list(texts))
        vectors = [list(item.embedding) for item in response.data]
        if len(vectors) != len(texts):
            raise RuntimeError("Embedding provider returned an unexpected number of vectors.")
        return vectors


def build_embeddings(
    provider: EmbeddingProvider | None, texts: Sequence[str], batch_size: int = 50
) -> list[list[float] | None]:
    """Embed text in bounded batches; no key intentionally selects keyword-only mode."""
    if provider is None:
        logger.info("OPENROUTER_API_KEY is unset; indexing without semantic vectors.")
        return [None] * len(texts)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(provider.embed(texts[start : start + batch_size]))
    return vectors
