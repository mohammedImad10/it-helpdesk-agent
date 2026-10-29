import pytest

from app.models import ToolCall
from app.retrieval.search import KnowledgeBase
from app.workflow import HelpdeskWorkflow


class FakeMcpClient:
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


@pytest.mark.asyncio
async def test_nx_403_returns_documented_steps_before_a_ticket(monkeypatch) -> None:
    monkeypatch.setattr("app.workflow.HelpdeskMcpClient", FakeMcpClient)
    workflow = HelpdeskWorkflow(KnowledgeBase.build())

    response = await workflow.chat(
        "nx-403-test",
        "My VPN shows NX-403 since this morning. I approved the NakhlaKey prompt twice.",
        "tariq.hamdan@nakhla.example",
    )

    assert response.pending_action is None
    assert "VPN-Users" in response.reply
    assert [citation.id for citation in response.citations] == ["KB-002", "KB-007"]


@pytest.mark.asyncio
async def test_unknown_issue_can_be_escalated_after_user_confirms(monkeypatch) -> None:
    monkeypatch.setattr("app.workflow.HelpdeskMcpClient", FakeMcpClient)
    workflow = HelpdeskWorkflow(KnowledgeBase.build())

    initial = await workflow.chat(
        "crm-escalation-test",
        "The NakhlaCRM mobile app shows error CRM-1150 every time it syncs my contacts.",
        "omar.farah@nakhla.example",
    )
    response = await workflow.chat(
        "crm-escalation-test",
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
