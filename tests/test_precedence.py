from dataclasses import asdict

from app.retrieval.precedence import eligible
from app.retrieval.search import Chunk, KnowledgeBase


def selected_ids(query: str, department: str | None = None) -> set[str]:
    kb = KnowledgeBase.build()
    return {chunk.metadata["id"] for chunk in kb.search(query, department)}


def test_deprecated_and_draft_documents_are_never_selected() -> None:
    ids = selected_ids("NX-781 NakhlaConnect")
    assert "KB-002" in ids
    assert "KB-001" not in ids
    assert "KB-018" not in ids


def test_security_policy_ranks_before_knowledge_base_articles() -> None:
    kb = KnowledgeBase.build()
    docs = [asdict(chunk) for chunk in kb.chunks if chunk.metadata["id"] in {"SP-001", "KB-004"}]
    assert eligible(docs)[0]["metadata"]["id"] == "SP-001"


def test_search_applies_policy_precedence_before_semantic_relevance() -> None:
    common_metadata = {
        "status": "current",
        "applies_to": ["all"],
        "authoritative": True,
        "last_updated": "2026-01-01",
        "version": "1.0",
        "error_codes": [],
    }
    kb = KnowledgeBase([
        Chunk(
            "Reset the password through the approved self-service portal.",
            {**common_metadata, "id": "SP-999"},
            "policy.md",
        ),
        Chunk(
            "Reset the password by calling the service desk.",
            {**common_metadata, "id": "KB-999"},
            "guide.md",
        ),
    ])
    results = kb.search("password reset")

    assert [chunk.metadata["id"] for chunk in results] == ["SP-999", "KB-999"]


def test_current_authoritative_priority_rule_beats_old_faq() -> None:
    kb = KnowledgeBase.build()
    docs = [asdict(chunk) for chunk in kb.chunks if chunk.metadata["id"] in {"KB-015", "KB-017"}]
    assert eligible(docs)[0]["metadata"]["id"] == "KB-015"


def test_pdf_and_mfa_sources_remain_current_and_citeable() -> None:
    ids = selected_ids("MFA backup code")
    assert "SP-002" in ids
    assert "KB-007" in ids
