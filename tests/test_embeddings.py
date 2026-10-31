from app.retrieval.search import Chunk, KnowledgeBase


class FakeEmbeddingProvider:
    model = "test-model"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "semantic query" in text or "VPN" in text else [0.0, 1.0] for text in texts]


class SemanticPdfProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0] if any(term in text.lower() for term in ("printer", "paper", "badge")) else [0.0, 1.0]
            for text in texts
        ]


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


def test_semantic_query_retrieves_pdf_only_printing_guidance(monkeypatch) -> None:
    provider = SemanticPdfProvider()
    monkeypatch.setattr(
        "app.retrieval.search.EmbeddingProvider.from_environment", lambda: provider
    )

    results = KnowledgeBase.build(embedding_provider=provider).search(
        "I cannot release my paper at the badge reader."
    )

    assert results[0].metadata["id"] == "KB-013"
    assert results[0].source_path.endswith(".pdf")


def test_load_or_build_reembeds_a_keyword_only_index_when_provider_is_available(
    monkeypatch, tmp_path
) -> None:
    provider = SemanticPdfProvider()
    monkeypatch.setattr("app.retrieval.search.VECTOR_DB_PATH", tmp_path / "chroma")
    KnowledgeBase([Chunk("keyword-only", current_metadata("KB-999"), "kb-999.md")]).persist()
    monkeypatch.setattr(
        "app.retrieval.search.EmbeddingProvider.from_environment", lambda: provider
    )

    kb = KnowledgeBase.load_or_build()

    assert kb.has_embeddings


def test_load_or_build_creates_a_missing_chroma_collection(monkeypatch, tmp_path) -> None:
    provider = SemanticPdfProvider()
    monkeypatch.setattr("app.retrieval.search.VECTOR_DB_PATH", tmp_path / "chroma")
    monkeypatch.setattr(
        "app.retrieval.search.EmbeddingProvider.from_environment", lambda: provider
    )

    kb = KnowledgeBase.load_or_build()

    assert kb.collection.count() == len(kb.chunks)
    assert kb.has_embeddings
