from app.retrieval.search import KnowledgeBase


def test_ingestion_preserves_required_metadata() -> None:
    kb = KnowledgeBase.build()
    assert len({chunk.metadata["id"] for chunk in kb.chunks}) == 20
    for chunk in kb.chunks:
        assert {"id", "title", "version", "status", "authoritative", "last_updated", "supersedes", "applies_to"} <= chunk.metadata.keys()
        assert chunk.source_path


def test_pdf_content_is_searchable() -> None:
    kb = KnowledgeBase.build()
    results = kb.search("PRN-07 printer")
    assert any(chunk.metadata["id"] == "KB-013" for chunk in results)
