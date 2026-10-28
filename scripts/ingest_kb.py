from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.retrieval.search import KnowledgeBase


if __name__ == "__main__":
    kb = KnowledgeBase.build()
    kb.persist()
    print(f"Indexed {len({chunk.metadata['id'] for chunk in kb.chunks})} documents in {len(kb.chunks)} sections.")
