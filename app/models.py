from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserContext(BaseModel):
    email: str | None = None


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    user: UserContext | None = None


class ApproveRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)
    action_id: str = Field(min_length=1, max_length=200)
    approved: bool


class Citation(BaseModel):
    id: str
    title: str
    url: str | None = None


class ToolCall(BaseModel):
    tool: str
    ok: bool
    ms: int = Field(ge=0)


class PendingAction(BaseModel):
    action_id: str
    type: Literal["create_ticket"]
    summary: str
    payload: dict[str, Any]


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    state: str | None = None
    pending_action: PendingAction | None = None
    result: dict[str, Any] | None = None
    citations: list[Citation] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)


Category = Literal[
    "network_access", "identity_access", "hardware", "software", "email_collab",
    "security", "onboarding", "other",
]
Department = Literal[
    "Engineering", "Finance", "HR", "Sales", "Support", "Executive Office", "Contractors",
]


class TicketDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=5, max_length=120)
    description: str = Field(min_length=10, max_length=4000)
    category: Category
    priority: Literal["P1", "P2", "P3", "P4"]
    requester_email: str = Field(pattern=r"^[a-z0-9._-]+@nakhla\.example$")
    department: Department
    attempted_steps: list[str] = Field(min_length=1, max_length=20)
    kb_refs: list[str] = Field(max_length=10)
    affected_users: int = Field(default=1, ge=1, le=1000)

    @field_validator("attempted_steps")
    @classmethod
    def validate_steps(cls, steps: list[str]) -> list[str]:
        if any(not 3 <= len(step) <= 300 for step in steps):
            raise ValueError("Each attempted step must contain 3 to 300 characters.")
        return steps

    @field_validator("kb_refs")
    @classmethod
    def validate_kb_refs(cls, refs: list[str]) -> list[str]:
        import re

        if len(set(refs)) != len(refs) or any(not re.fullmatch(r"(?:KB|SP)-\d{3}", ref) for ref in refs):
            raise ValueError("KB references must be unique KB- or SP- ids.")
        return refs
