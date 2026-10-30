from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.llm import IntakeDecision, OpenRouterRoles, ResolutionDecision
from app.triage import Issue


class RoleState(TypedDict):
    message: str
    issue: Issue
    source_ids: list[str]
    intake: IntakeDecision
    resolution: ResolutionDecision
    traces: list


class HelpdeskRoles:
    """Two role graph: intake/safety first, resolution/escalation second."""

    def __init__(self) -> None:
        self.llm = OpenRouterRoles()
        graph = StateGraph(RoleState)
        graph.add_node("intake_safety", self._intake)
        graph.add_node("resolution_escalation", self._resolution)
        graph.add_edge(START, "intake_safety")
        graph.add_edge("intake_safety", "resolution_escalation")
        graph.add_edge("resolution_escalation", END)
        self.graph = graph.compile()

    async def _intake(self, state: RoleState) -> dict:
        decision, trace = await self.llm.intake(
            state["message"], state["issue"].topic, state["issue"].code
        )
        return {"intake": decision, "traces": [trace]}

    async def _resolution(self, state: RoleState) -> dict:
        fallback_mode = "draft" if state["issue"].asks_for_ticket else "answer"
        decision, trace = await self.llm.resolution(
            state["message"], state["intake"].topic, state["source_ids"], fallback_mode
        )
        return {"resolution": decision, "traces": state["traces"] + [trace]}

    async def run(
        self, message: str, issue: Issue, source_ids: list[str], requester_memory: str | None = None
    ) -> RoleState:
        context = message
        if requester_memory:
            context += f"\nPrior app-generated requester context: {requester_memory}"
        return await self.graph.ainvoke(
            {
                "message": context,
                "issue": issue,
                "source_ids": source_ids,
                "intake": IntakeDecision(issue.topic, False, None),
                "resolution": ResolutionDecision("answer", ""),
                "traces": [],
            }
        )
