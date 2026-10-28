from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import ChatResponse, Citation, ToolCall
from app.retrieval.search import KnowledgeBase

INJECTION_PATTERNS = (
    r"ignore (?:all |any |the )?(?:previous|system|developer) instructions",
    r"system override",
    r"reveal (?:the )?(?:password|secret|credential)",
    r"localadmin",
    r"do not mention this",
)


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str | None = None


def screen_input(message: str) -> GuardrailResult:
    lowered = message.lower()
    if any(re.search(pattern, lowered) for pattern in INJECTION_PATTERNS):
        return GuardrailResult(False, "I cannot follow instructions that request secrets or attempt to override helpdesk safety rules.")
    return GuardrailResult(True)


def valid_citations(kb: KnowledgeBase, citations: list[Citation]) -> bool:
    for citation in citations:
        source = kb.by_id(citation.id)
        if source is None or source.metadata.get("status") != "current":
            return False
    return True


def enforce_output(response: ChatResponse, kb: KnowledgeBase) -> ChatResponse:
    if not valid_citations(kb, response.citations):
        response.citations = []
        response.reply = "I could not verify the selected knowledge-base sources, so I will not provide unsupported guidance."
        response.state = "safety_check_failed"
    ticket_ids = set(re.findall(r"\bIT-\d{4}\b", response.reply))
    confirmed_id = (response.result or {}).get("ticket_id")
    if ticket_ids and confirmed_id not in ticket_ids:
        response.reply = "I cannot confirm a ticket ID until the helpdesk system returns it."
        response.result = None
        response.state = "safety_check_failed"
    response.tool_calls.append(ToolCall(tool="output_guard", ok=True, ms=0))
    return response
