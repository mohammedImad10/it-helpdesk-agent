import uuid

import pytest

from app.approval import approve
from app.models import PendingAction, TicketDraft, ToolCall
from app.services.sessions import StoredAction, sessions


def _draft() -> TicketDraft:
    return TicketDraft(
        subject="NX-112 VPN issue",
        description="NakhlaConnect shows NX-112 and is blocking work.",
        category="network_access",
        priority="P2",
        requester_email="sara.mikhail@nakhla.example",
        department="Support",
        attempted_steps=["Ran NakhlaManage Sync."],
        kb_refs=["KB-002"],
    )


class RetryMcpClient:
    calls = 0

    async def create_ticket(self, draft: dict, idempotency_key: str):
        type(self).calls += 1
        if type(self).calls == 1:
            return (
                {"ok": False, "error": {"message": "Service unavailable"}},
                ToolCall(tool="create_ticket", ok=False, ms=1),
            )
        return (
            {"ok": True, "ticket": {"ticket_id": "IT-3001"}},
            ToolCall(tool="create_ticket", ok=True, ms=1),
        )


@pytest.mark.asyncio
async def test_rejected_action_never_calls_ticket_system() -> None:
    draft = _draft()
    action = PendingAction(
        action_id="act-reject-test",
        type="create_ticket",
        summary="Create the test ticket.",
        payload={},
    )
    sessions.put_action("approval-test", StoredAction(action=action, draft=draft))

    response = await approve("approval-test", action.action_id, False)

    assert response.result is None
    assert response.pending_action is None
    assert "not create" in response.reply.lower()
    assert sessions.get("approval-test").decision == "ticket_rejected"


@pytest.mark.asyncio
async def test_unknown_approval_never_claims_success() -> None:
    response = await approve("approval-test", "act-unknown", True)

    assert response.result is None
    assert "unknown" in response.reply.lower()


@pytest.mark.asyncio
async def test_failed_ticket_write_can_be_retried(monkeypatch) -> None:
    monkeypatch.setattr("app.approval.HelpdeskMcpClient", RetryMcpClient)
    session_id = f"approval-retry-test-{uuid.uuid4()}"
    action = PendingAction(
        action_id=f"act-retry-{uuid.uuid4()}",
        type="create_ticket",
        summary="Create the retry ticket.",
        payload={},
    )
    sessions.put_action(session_id, StoredAction(action=action, draft=_draft()))
    RetryMcpClient.calls = 0

    failed = await approve(session_id, action.action_id, True)
    assert failed.state == "await_confirmation"
    assert sessions.get_action(session_id, action.action_id).consumed is False
    assert sessions.get(session_id).decision == "ticket_write_failed"

    succeeded = await approve(session_id, action.action_id, True)

    assert sessions.get_action(session_id, action.action_id).consumed is True
    assert succeeded.result == {"ticket_id": "IT-3001"}
    assert RetryMcpClient.calls == 2
    assert sessions.get(session_id).decision == "ticket_created"
