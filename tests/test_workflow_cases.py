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
