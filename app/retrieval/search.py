from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fitz
import yaml

from app.config import INDEX_PATH, KB_ROOT
from app.retrieval.precedence import eligible


@dataclass
class Chunk:
    text: str
    metadata: dict[str, Any]
    source_path: str


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
    def build(cls, source: Path = KB_ROOT) -> "KnowledgeBase":
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
        return cls(chunks)

    @classmethod
    def load_or_build(cls) -> "KnowledgeBase":
        if INDEX_PATH.exists():
            saved = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            return cls([Chunk(**item) for item in saved])
        kb = cls.build()
        kb.persist()
        return kb

    def persist(self) -> None:
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        INDEX_PATH.write_text(json.dumps([asdict(chunk) for chunk in self.chunks], default=str), encoding="utf-8")

    def search(self, query: str, department: str | None = None, limit: int = 5) -> list[Chunk]:
        terms = set(re.findall(r"[a-z0-9-]+", query.lower()))
        error_codes = set(re.findall(r"\b[A-Z]{2,4}-\d{2,4}\b", query.upper()))
        candidates = eligible([asdict(chunk) for chunk in self.chunks], department)

        def score(item: dict[str, Any]) -> tuple[int, int, str]:
            chunk = item["text"].lower()
            meta = item["metadata"]
            exact = len(error_codes.intersection(set(meta.get("error_codes") or [])))
            words = sum(term in chunk for term in terms if len(term) > 2)
            return exact, words, str(meta["id"])

        matching = [item for item in candidates if score(item)[:2] != (0, 0)]
        return [Chunk(**item) for item in sorted(matching, key=score, reverse=True)[:limit]]

    def by_id(self, doc_id: str) -> Chunk | None:
        return next((chunk for chunk in self.chunks if chunk.metadata["id"] == doc_id), None)
