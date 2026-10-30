import uuid

import pytest

from app.approval import approve
from app.models import ToolCall
from app.retrieval.search import KnowledgeBase
from app.services.sessions import sessions
from app.workflow import HelpdeskWorkflow


class FakeMcpClient:
    create_calls = 0

    async def lookup_employee(self, email: str):
        return (
            {
                "ok": True,
                "employee": {
                    "email": email,
                    "department": "Engineering",
                    "vip": False,
                },
            },
            ToolCall(tool="lookup_employee", ok=True, ms=1),
        )

    async def get_service_status(self):
        return (
            {"ok": True, "status": {"incidents": []}},
            ToolCall(tool="get_service_status", ok=True, ms=1),
        )

    async def create_ticket(self, draft: dict, idempotency_key: str):
        type(self).create_calls += 1
        return (
            {"ok": True, "ticket": {"ticket_id": "IT-2001"}},
            ToolCall(tool="create_ticket", ok=True, ms=1),
        )


class ActiveIncidentMcpClient(FakeMcpClient):
    async def get_service_status(self):
        return (
            {
                "ok": True,
                "status": {
                    "incidents": [
                        {
                            "id": "INC-100",
                            "status": "active",
                            "title": "VPN outage",
                            "workaround": "Use VDI.",
                            "instructions": "Wait for the incident update.",
                            "error_codes": ["NX-403"],
                        }
                    ]
                },
            },
            ToolCall(tool="get_service_status", ok=True, ms=1),
        )


@pytest.mark.asyncio
async def test_nx_403_returns_documented_steps_before_a_ticket(monkeypatch) -> None:
    monkeypatch.setattr("app.workflow.HelpdeskMcpClient", FakeMcpClient)
    workflow = HelpdeskWorkflow(KnowledgeBase.build())
    session_id = f"nx-403-test-{uuid.uuid4()}"

    response = await workflow.chat(
        session_id,
        "My VPN shows NX-403 since this morning. I approved the NakhlaKey prompt twice.",
        "tariq.hamdan@nakhla.example",
    )

    assert response.pending_action is None
    assert "VPN-Users" in response.reply
    assert [citation.id for citation in response.citations] == ["KB-002", "KB-007"]
    assert sessions.get(session_id).decision == "worked_confirmation"


@pytest.mark.asyncio
async def test_unknown_issue_can_be_escalated_after_user_confirms(monkeypatch) -> None:
    monkeypatch.setattr("app.workflow.HelpdeskMcpClient", FakeMcpClient)
    workflow = HelpdeskWorkflow(KnowledgeBase.build())
    session_id = f"crm-escalation-test-{uuid.uuid4()}"

    initial = await workflow.chat(
        session_id,
        "The NakhlaCRM mobile app shows error CRM-1150 every time it syncs my contacts.",
        "omar.farah@nakhla.example",
    )
    response = await workflow.chat(
        session_id,
        "Yes, please create a ticket.",
        None,
    )

    assert initial.state == "unknown_issue"
    assert response.pending_action is not None
    assert response.pending_action.type == "create_ticket"
    assert response.pending_action.payload["category"] == "other"
    assert response.pending_action.payload["priority"] == "P3"
    assert response.pending_action.payload["kb_refs"] == []
    assert "CRM-1150" in response.pending_action.payload["description"]
    assert sessions.get(session_id).decision == "draft_pending_approval"


@pytest.mark.asyncio
async def test_missing_context_and_evidence_are_persisted(monkeypatch) -> None:
    monkeypatch.setattr("app.workflow.HelpdeskMcpClient", FakeMcpClient)
    workflow = HelpdeskWorkflow(KnowledgeBase.build())
    context_session_id = f"missing-context-test-{uuid.uuid4()}"
    evidence_session_id = f"evidence-test-{uuid.uuid4()}"

    context_response = await workflow.chat(context_session_id, "My VPN will not connect.", None)
    evidence_response = await workflow.chat(
        evidence_session_id,
        "Software Center shows SWC-2001.",
        "evidence@nakhla.example",
    )

    assert context_response.state == "awaiting_context"
    assert sessions.get(context_session_id).decision == "missing_context"
    assert evidence_response.state == "review_required"
    assert sessions.get(evidence_session_id).decision == "evidence"


@pytest.mark.asyncio
async def test_active_incident_is_persisted(monkeypatch) -> None:
    monkeypatch.setattr("app.workflow.HelpdeskMcpClient", ActiveIncidentMcpClient)
    workflow = HelpdeskWorkflow(KnowledgeBase.build())
    session_id = f"active-incident-test-{uuid.uuid4()}"

    response = await workflow.chat(
        session_id,
        "My VPN shows NX-403.",
        "incident@nakhla.example",
    )

    assert response.state == "active_incident"
    assert sessions.get(session_id).decision == "active_incident"


@pytest.mark.asyncio
async def test_documented_fix_follow_up_saves_resolution_memory(monkeypatch) -> None:
    monkeypatch.setattr("app.workflow.HelpdeskMcpClient", FakeMcpClient)
    workflow = HelpdeskWorkflow(KnowledgeBase.build())
    email = "follow-up-worked@nakhla.example"
    session_id = f"documented-worked-test-{uuid.uuid4()}"

    initial = await workflow.chat(
        session_id,
        "My VPN shows NX-403.",
        email,
    )
    response = await workflow.chat(session_id, "It worked.", None)

    assert initial.state == "awaiting_follow_up"
    assert response.state == "resolved"
    assert sessions.memory_for(email) == (
        "Resolved NX-403 using the documented troubleshooting procedure.",
        None,
    )


@pytest.mark.asyncio
async def test_documented_fix_failure_requires_escalation_and_approval(monkeypatch) -> None:
    monkeypatch.setattr("app.workflow.HelpdeskMcpClient", FakeMcpClient)
    monkeypatch.setattr("app.approval.HelpdeskMcpClient", FakeMcpClient)
    workflow = HelpdeskWorkflow(KnowledgeBase.build())
    session_id = f"documented-escalation-test-{uuid.uuid4()}"
    FakeMcpClient.create_calls = 0

    initial = await workflow.chat(
        session_id,
        "My VPN shows NX-403 and blocks my work.",
        "follow-up-failed@nakhla.example",
    )
    declined = await workflow.chat(session_id, "It did not work.", None)
    draft = await workflow.chat(session_id, "Yes, prepare the ticket.", None)

    assert initial.state == "awaiting_follow_up"
    assert declined.state == "escalation_offered"
    assert draft.pending_action is not None
    assert FakeMcpClient.create_calls == 0
    approval = await approve(session_id, draft.pending_action.action_id, True)

    assert approval.result == {"ticket_id": "IT-2001"}
    assert "created" in approval.reply.lower()
    assert FakeMcpClient.create_calls == 1
