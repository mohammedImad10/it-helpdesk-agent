from app.retrieval.search import Chunk, KnowledgeBase


class FakeEmbeddingProvider:
    model = "test-model"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "semantic query" in text or "VPN" in text else [0.0, 1.0] for text in texts]


def current_metadata(doc_id: str) -> dict:
    return {
        "id": doc_id,
        "title": doc_id,
        "status": "current",
        "authoritative": True,
        "last_updated": "2026-10-01",
        "version": "1.0",
        "applies_to": ["all"],
        "error_codes": [],
    }


def test_ingestion_stores_embedding_vectors(monkeypatch) -> None:
    provider = FakeEmbeddingProvider()
    monkeypatch.setattr(
        "app.retrieval.search.EmbeddingProvider.from_environment", lambda: provider
    )
    chunks = [
        Chunk("VPN connection guidance", current_metadata("KB-002"), "kb-002.md", [1.0, 0.0]),
        Chunk("Printer guidance", current_metadata("KB-013"), "kb-013.md", [0.0, 1.0]),
    ]

    results = KnowledgeBase(chunks).search("semantic query")

    assert results[0].metadata["id"] == "KB-002"
