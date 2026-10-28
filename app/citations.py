from __future__ import annotations

from app.models import Citation
from app.retrieval.search import KnowledgeBase


def citations_for(kb: KnowledgeBase, *ids: str) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for doc_id in ids:
        if doc_id in seen:
            continue
        chunk = kb.by_id(doc_id)
        if chunk is not None and chunk.metadata.get("status") == "current":
            citations.append(Citation(id=doc_id, title=str(chunk.metadata["title"])))
            seen.add(doc_id)
    return citations
