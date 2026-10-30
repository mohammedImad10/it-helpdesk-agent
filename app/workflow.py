from __future__ import annotations

import re
import uuid
from typing import Any

from app.agent_graph import HelpdeskRoles
from app.citations import citations_for
from app.guardrails import screen_input
from app.mcp_client import HelpdeskMcpClient
from app.models import ChatResponse, Citation, PendingAction, TicketDraft, ToolCall
from app.retrieval.search import KnowledgeBase
from app.services.sessions import StoredAction, sessions
from app.triage import Issue, extract_issue


class HelpdeskWorkflow:
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.kb = knowledge_base
        self.roles = HelpdeskRoles()

    def _citation(self, *ids: str) -> list[Citation]:
        return citations_for(self.kb, *ids)

    @staticmethod
    def _incident(status: dict[str, Any], issue: Issue) -> dict[str, Any] | None:
        for incident in status.get("status", {}).get("incidents", []):
            if incident.get("status") != "active":
                continue
            if issue.code and issue.code in incident.get("error_codes", []):
                return incident
        return None

    @staticmethod
    def _attempted_steps(message: str, code: str | None) -> list[str]:
        lowered = message.lower()
        steps: list[str] = []
        for phrase in ("sync", "restart", "restarted", "compliant", "another cable", "updated"):
            if phrase in lowered:
                steps.append(f"Employee reported: {phrase}.")
        return steps or [f"Employee reported {code or 'the issue'} and requested help."]

    @staticmethod
    def _accepts_escalation(message: str) -> bool:
        return bool(
            re.search(
                r"\b(?:yes|please|go ahead|do it|open|create|file|raise|prepare)\b",
                message.lower(),
            )
        )

    @staticmethod
    def _reports_worked(message: str) -> bool:
        return bool(
            re.search(
                r"\b(?:yes(?:,? it did)?|it worked|worked|fixed|resolved|all set)\b",
                message.lower(),
            )
        )

    @staticmethod
    def _reports_not_worked(message: str) -> bool:
        return bool(
            re.search(
                r"\b(?:no|not working|did not work|didn't work|still (?:broken|failing|not working)|problem persists)\b",
                message.lower(),
            )
        )

    @staticmethod
    def _escalation_category(issue: Issue) -> str:
        return {
            "vpn": "network_access",
            "identity": "identity_access",
            "software": "software",
            "hardware": "hardware",
        }.get(issue.topic, "other")

    def _documented_response(
        self,
        session_id: str,
        session: Any,
        issue: Issue,
        reported_message: str,
        reply: str,
        refs: list[str],
        traces: list[ToolCall],
    ) -> ChatResponse:
        session.issue = {
            "code": issue.code,
            "topic": issue.topic,
            "reported_message": reported_message,
            "kb_refs": refs,
        }
        session.awaiting = "worked_confirmation"
        sessions.save(session_id, session)
        return ChatResponse(
            session_id=session_id,
            reply=f"{reply} Did that resolve the issue?",
            state="awaiting_follow_up",
            citations=self._citation(*refs),
            tool_calls=traces,
        )

    def _draft(
        self,
        session_id: str,
        message: str,
        issue: Issue,
        employee: dict[str, Any],
        category: str,
        priority: str,
        refs: list[str],
    ) -> ChatResponse:
        draft = TicketDraft(
            subject=(f"{issue.code}: {issue.topic.replace('_', ' ')} issue" if issue.code else f"{issue.topic.title()} support request"),
            description=message[:4000],
            category=category,
            priority=priority,
            requester_email=employee["email"].lower(),
            department=employee["department"],
            attempted_steps=self._attempted_steps(message, issue.code),
            kb_refs=refs,
            affected_users=issue.affected_users,
        )
        action = PendingAction(
            action_id=f"act-{uuid.uuid4().hex}",
            type="create_ticket",
            summary=(
                f"Create a {draft.priority} {draft.category} ticket for {draft.requester_email}: "
                f"{draft.subject}. Attempted steps: {'; '.join(draft.attempted_steps)}."
            ),
            payload=draft.model_dump(),
        )
        sessions.put_action(session_id, StoredAction(action=action, draft=draft))
        return ChatResponse(
            session_id=session_id,
            reply=f"I prepared this ticket for your approval: {action.summary}",
            state="await_confirmation",
            pending_action=action,
            citations=self._citation(*refs),
        )

    async def chat(self, session_id: str, message: str, email: str | None) -> ChatResponse:
        guard = screen_input(message)
        guard_trace = ToolCall(tool="input_guard", ok=guard.allowed, ms=0)
        if not guard.allowed:
            return ChatResponse(
                session_id=session_id,
                reply=guard.reason or "I cannot process that request safely.",
                state="guardrail_blocked",
                tool_calls=[guard_trace],
            )
        session = sessions.get(session_id)
        awaiting_worked = session.awaiting == "worked_confirmation"
        awaiting_escalation = session.awaiting == "escalation_confirmation"
        reported_message = (
            str(session.issue.get("reported_message", message))
            if awaiting_escalation
            else message
        )
        if email:
            session.email = email.lower()
            sessions.save(session_id, session)
        if awaiting_worked:
            if self._reports_worked(message):
                summary = (
                    f"Resolved {session.issue.get('code') or session.issue.get('topic', 'support issue')} "
                    "using the documented troubleshooting procedure."
                )
                if session.email:
                    sessions.remember(session.email, summary)
                session.awaiting = None
                sessions.save(session_id, session)
                return ChatResponse(
                    session_id=session_id,
                    reply="I'm glad that resolved it. I recorded the resolution for future support.",
                    state="resolved",
                    citations=self._citation(*[str(ref) for ref in session.issue.get("kb_refs", [])]),
                    tool_calls=[guard_trace],
                )
            if self._reports_not_worked(message):
                session.awaiting = "escalation_confirmation"
                sessions.save(session_id, session)
                return ChatResponse(
                    session_id=session_id,
                    reply="I'm sorry that did not resolve it. Would you like me to prepare an escalation ticket for your approval?",
                    state="escalation_offered",
                    citations=self._citation(*[str(ref) for ref in session.issue.get("kb_refs", [])]),
                    tool_calls=[guard_trace],
                )
            return ChatResponse(
                session_id=session_id,
                reply="Did the documented procedure resolve the issue? Please reply yes or no.",
                state="awaiting_follow_up",
                citations=self._citation(*[str(ref) for ref in session.issue.get("kb_refs", [])]),
                tool_calls=[guard_trace],
            )
        issue = extract_issue(message)
        if issue.code is None and session.issue.get("code"):
            issue = Issue(
                code=str(session.issue["code"]),
                topic=str(session.issue["topic"]),
                asks_for_ticket=issue.asks_for_ticket,
                affected_users=issue.affected_users,
            )
        if issue.code is None and issue.topic == "vpn":
            session.awaiting = "error_code"
            return ChatResponse(
                session_id=session_id,
                reply="What error code does NakhlaConnect show (for example NX-403), and what is your Nakhla work email?",
                state="awaiting_context",
                tool_calls=[guard_trace],
            )
        if not session.email:
            session.awaiting = "email"
            return ChatResponse(
                session_id=session_id,
                reply="Please provide your Nakhla work email so I can check the applicable department and device rules.",
                state="awaiting_context",
                tool_calls=[guard_trace],
            )

        client = HelpdeskMcpClient()
        employee_result, employee_trace = await client.lookup_employee(session.email)
        traces: list[ToolCall] = [guard_trace, employee_trace]
        if not employee_result.get("ok"):
            return ChatResponse(
                session_id=session_id,
                reply="I could not verify your employee details, so I cannot safely apply department rules yet.",
                state="awaiting_context",
                tool_calls=traces,
            )
        employee = employee_result["employee"]
        status_result, status_trace = await client.get_service_status()
        traces.append(status_trace)
        if not status_result.get("ok"):
            return ChatResponse(
                session_id=session_id,
                reply="I could not check the live service status, so I will not provide troubleshooting or create a ticket yet.",
                state="status_unavailable",
                tool_calls=traces,
            )
        if awaiting_escalation:
            stored_issue = session.issue
            issue = Issue(
                code=str(stored_issue["code"]) if stored_issue.get("code") else None,
                topic=str(stored_issue.get("topic", "other")),
                asks_for_ticket=False,
                affected_users=1,
            )
            refs = [str(ref) for ref in stored_issue.get("kb_refs", [])]
            if self._accepts_escalation(message):
                session.awaiting = None
                sessions.save(session_id, session)
                response = self._draft(
                    session_id,
                    reported_message,
                    issue,
                    employee,
                    self._escalation_category(issue),
                    "P1" if employee["vip"] else "P3",
                    refs,
                )
                response.tool_calls = traces
                return response
            return ChatResponse(
                session_id=session_id,
                reply="I will not create a ticket unless you ask me to prepare one for approval.",
                state="escalation_offered",
                citations=self._citation(*refs),
                tool_calls=traces,
            )

        source_ids = [chunk.metadata["id"] for chunk in self.kb.search(message, employee["department"])]
        requester_memory = sessions.memory_for(employee["email"])
        role_state = await self.roles.run(
            message,
            issue,
            source_ids,
            requester_memory[0] if requester_memory else None,
        )
        traces.extend(role_state["traces"])
        role_topic = role_state["intake"].topic
        issue = Issue(
            code=issue.code,
            topic=role_topic,
            asks_for_ticket=issue.asks_for_ticket,
            affected_users=issue.affected_users,
        )
        session.issue = {
            "code": issue.code,
            "topic": issue.topic,
            "reported_message": reported_message,
        }
        session.awaiting = None
        sessions.save(session_id, session)
        incident = self._incident(status_result, issue)
        if incident is not None:
            return ChatResponse(
                session_id=session_id,
                reply=f"{incident['id']} is an active incident: {incident['title']}. {incident['workaround']} {incident['instructions']}",
                state="active_incident",
                tool_calls=traces,
            )

        if issue.topic == "vpn" and employee["department"] == "Contractors":
            return ChatResponse(
                session_id=session_id,
                reply="Contractors do not receive VPN access. Use the Nakhla Workspace VDI portal at https://vdi.nakhla.example; VPN access requests are refused and no ticket is needed.",
                state="resolved",
                citations=self._citation("SP-002", "KB-016"),
                tool_calls=traces,
            )

        if issue.topic == "vpn" and employee["department"] == "Finance":
            response = self._draft(
                session_id, message, issue, employee, "security",
                "P1" if issue.affected_users > 3 else "P2", ["KB-016", "KB-002"],
            )
            response.reply = (
                "Finance VPN problems must go directly to Security Operations; I will not provide client troubleshooting. "
                + response.reply
            )
            response.tool_calls = traces
            return response

        if issue.code == "NID-423":
            return self._documented_response(
                session_id, session, issue, reported_message,
                (
                    "Your account locks after five failed sign-ins in 15 minutes. Wait 30 minutes for it to unlock, "
                    "or unlock it now at https://id.nakhla.example/unlock and approve the NakhlaKey prompt."
                ),
                ["KB-006"], traces,
            )

        if issue.code == "NX-781":
            return self._documented_response(
                session_id, session, issue, reported_message,
                (
                    "NX-781 means your NakhlaConnect client is below the supported version. Update to 5.4.2 from "
                    "Software Center, then restart NakhlaConnect. Do not bypass the version check."
                ),
                ["KB-002", "SP-002"], traces,
            )

        if issue.code == "NX-112":
            if issue.asks_for_ticket:
                response = self._draft(
                    session_id, message, issue, employee, "network_access",
                    "P1" if issue.affected_users > 3 or employee["vip"] else "P2", ["KB-002"],
                )
                response.tool_calls = traces
                return response
            return self._documented_response(
                session_id, session, issue, reported_message,
                (
                    "For NX-112, open NakhlaManage and run Sync, restart the laptop, then check it is compliant. "
                    "A device offline for more than 30 days must sync before VPN works."
                ),
                ["KB-002"], traces,
            )

        if issue.code == "NX-403":
            if issue.asks_for_ticket:
                response = self._draft(
                    session_id, message, issue, employee, "network_access",
                    "P1" if issue.affected_users > 3 or employee["vip"] else "P2", ["KB-002"],
                )
                response.tool_calls = traces
                return response
            return self._documented_response(
                session_id, session, issue, reported_message,
                (
                    "NX-403 means access was denied. Approve the NakhlaKey prompt within 60 seconds, "
                    "confirm you are enrolled in NakhlaKey, and ask for the VPN-Users access request "
                    "if you are new or recently transferred. A disabled account can also show NX-403."
                ),
                ["KB-002", "KB-007"], traces,
            )

        if issue.topic == "software" and issue.asks_for_ticket:
            response = self._draft(
                session_id, message, issue, employee, "software",
                "P1" if employee["vip"] else "P3", ["KB-009"],
            )
            response.tool_calls = traces
            return response
        if issue.topic == "hardware" and issue.asks_for_ticket:
            response = self._draft(
                session_id, message, issue, employee, "hardware",
                "P1" if employee["vip"] else "P3", ["KB-010"],
            )
            response.tool_calls = traces
            return response

        found = self.kb.search(message, employee["department"])
        documented_code = any(issue.code in chunk.metadata.get("error_codes", []) for chunk in found) if issue.code else False
        if found and documented_code:
            selected = found[0]
            return ChatResponse(
                session_id=session_id,
                reply=f"I found {selected.metadata['id']}, but this issue needs the documented procedure reviewed before I give steps.",
                state="review_required",
                citations=self._citation(str(selected.metadata["id"])),
                tool_calls=traces,
            )
        session.awaiting = "escalation_confirmation"
        sessions.save(session_id, session)
        return ChatResponse(
            session_id=session_id,
            reply="The knowledge base has no documented fix for this issue. I will not invent troubleshooting steps; I can prepare an escalation ticket if you want.",
            state="unknown_issue",
            tool_calls=traces,
        )
