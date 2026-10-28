from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    code: str | None
    topic: str
    asks_for_ticket: bool
    affected_users: int


def extract_issue(message: str) -> Issue:
    lowered = message.lower()
    codes = re.findall(r"\b[A-Z]{2,4}-\d{2,4}\b", message.upper())
    code = codes[0] if codes else None
    topic = "other"
    if "vpn" in lowered or "nakhlaconnect" in lowered or (code and code.startswith("NX-")):
        topic = "vpn"
    elif "password" in lowered or "sign in" in lowered or (code and code.startswith("NID-")):
        topic = "identity"
    elif "software center" in lowered or (code and code.startswith("SWC-")):
        topic = "software"
    elif "dock" in lowered or "monitor" in lowered or "laptop" in lowered:
        topic = "hardware"
    elif "print" in lowered or (code and code.startswith("PRN-")):
        topic = "printing"
    affected = re.search(r"\b(\d+)\s+(?:users?|people|colleagues?)\b", lowered)
    return Issue(
        code=code,
        topic=topic,
        asks_for_ticket=bool(re.search(r"\b(?:open|create|file|raise|prepare)\b.{0,30}\bticket\b", lowered)),
        affected_users=int(affected.group(1)) if affected else 1,
    )
