from __future__ import annotations

from app.mcp_client import HelpdeskMcpClient
from app.models import ChatResponse, ToolCall
from app.services.sessions import sessions


async def approve(session_id: str, action_id: str, approved: bool) -> ChatResponse:
    stored = sessions.get_action(session_id, action_id)
    if stored is None:
        return ChatResponse(
            session_id=session_id,
            reply="That ticket action is unknown or no longer available. Nothing was created.",
            state="idle",
        )
    if stored.consumed:
        return ChatResponse(
            session_id=session_id,
            reply="That ticket action was already used. No additional ticket was created.",
            state="idle",
        )
    if not approved:
        sessions.consume_action(action_id)
        session = sessions.get(session_id)
        session.awaiting = None
        session.decision = "ticket_rejected"
        sessions.save(session_id, session)
        return ChatResponse(
            session_id=session_id,
            reply="I will not create that ticket. Nothing was written to the helpdesk.",
            state="idle",
        )

    client = HelpdeskMcpClient()
    payload, trace = await client.create_ticket(stored.draft.model_dump(), action_id)
    if not payload.get("ok"):
        message = payload.get("error", {}).get("message", "The helpdesk ticket service was unavailable.")
        session = sessions.get(session_id)
        session.awaiting = "approval"
        session.decision = "ticket_write_failed"
        sessions.save(session_id, session)
        return ChatResponse(
            session_id=session_id,
            reply=f"The ticket was not created: {message} You can try approving this draft again.",
            state="await_confirmation",
            pending_action=stored.action,
            tool_calls=[trace],
        )

    sessions.consume_action(action_id)
    ticket_id = payload["ticket"]["ticket_id"]
    sessions.remember(
        stored.draft.requester_email,
        f"Created {ticket_id} for {stored.draft.subject}.",
        ticket_id,
    )
    session = sessions.get(session_id)
    session.awaiting = None
    session.decision = "ticket_created"
    sessions.save(session_id, session)
    return ChatResponse(
        session_id=session_id,
        reply=f"Your ticket {ticket_id} was created. The assigned team will contact you.",
        state="idle",
        result={"ticket_id": ticket_id},
        tool_calls=[trace],
    )
