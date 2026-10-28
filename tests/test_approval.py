import pytest

from app.approval import approve
from app.models import PendingAction, TicketDraft
from app.services.sessions import StoredAction, sessions


@pytest.mark.asyncio
async def test_rejected_action_never_calls_ticket_system() -> None:
    draft = TicketDraft(
        subject="NX-112 VPN issue",
        description="NakhlaConnect shows NX-112 and is blocking work.",
        category="network_access",
        priority="P2",
        requester_email="sara.mikhail@nakhla.example",
        department="Support",
        attempted_steps=["Ran NakhlaManage Sync."],
        kb_refs=["KB-002"],
    )
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


@pytest.mark.asyncio
async def test_unknown_approval_never_claims_success() -> None:
    response = await approve("approval-test", "act-unknown", True)

    assert response.result is None
    assert "unknown" in response.reply.lower()
