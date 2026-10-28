from __future__ import annotations

from datetime import date
from typing import Any


def eligible(documents: list[dict[str, Any]], department: str | None = None) -> list[dict[str, Any]]:
    """Return citeable documents in deterministic policy-precedence order."""
    current = [doc for doc in documents if doc["metadata"].get("status") == "current"]

    def rank(doc: dict[str, Any]) -> tuple[int, int, int, int, tuple[int, ...], str]:
        meta = doc["metadata"]
        is_policy = int(str(meta["id"]).startswith("SP-"))
        applies = meta.get("applies_to") or ["all"]
        department_specific = int(department is not None and department in applies)
        version = tuple(int(part) for part in str(meta.get("version", "0")).split("."))
        updated = meta.get("last_updated")
        if not isinstance(updated, date):
            updated = date.fromisoformat(str(updated))
        return (
            -is_policy,
            -department_specific,
            -int(bool(meta.get("authoritative"))),
            -updated.toordinal(),
            tuple(-part for part in version),
            str(meta["id"]),
        )

    return sorted(current, key=rank)
