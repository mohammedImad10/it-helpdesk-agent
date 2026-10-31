# DESIGN.md — Nakhla IT Helpdesk Agent

**Team:** `<add team member>` (agent engineer) · `<add team member>` (platform engineer)  
**Brief:** 2 — IT Helpdesk  
**Repo:** `<add public GitHub repository URL>`

## 1. The job, in one sentence

Nakhla employees get cited, policy-safe help for IT problems and may create a real simulated
helpdesk ticket only after approving its exact draft.

## 2. Architecture sketch

![Architecture](docs/architecture.svg)

The Gradio UI calls only the FastAPI contract. A chat request is screened before it restores
SQLite state, reads employee and status data through MCP, retrieves current KB evidence from
Chroma using exact error-code and semantic-vector ranking, then runs Intake & Safety followed by Resolution &
Escalation. Python remains the authority for precedence, policy, citations, and approval. The
separate `/api/approve` path loads the stored draft and is the only path that can send an approved
MCP write to the simulated Helpdesk API.

## 3. Roles

| Role | Its one job | Tools it may call | Done when |
|---|---|---|---|
| Intake & Safety | Extract intent, reject injection/out-of-scope requests, identify one missing fact | Read-only employee/status context supplied by orchestration | The workflow has safe, sufficient context |
| Resolution & Escalation | Select an answer, escalation offer, or draft route | Current selected KB context only; no write tools | Its mode changes safe response routing while Python validates the result |

`create_ticket` is called by application code in `/api/approve`, never by an LLM. **Agreed.**

## 4. State

Each session stores `email`, current issue code/topic, `awaiting` input, an explicit `decision`
state, and pending actions. Decision states cover missing context, evidence, active incident,
worked confirmation, escalation choice, draft pending approval, rejection, write failure, and
confirmed ticket creation. State lives in SQLite and is restored after an application restart.

## 5. Persistent memory

Requester memory is keyed by employee email. On successful ticket creation, the agent stores a
summary and real ticket ID; later sessions can read it to preserve relevant support context.

## 6. Guardrails

| Risk | Code check | Where |
|---|---|---|
| Prompt injection or secret requests | Reject override/credential patterns | Before roles or MCP |
| Poisoned/draft retrieval | Only `current` sources may be selected/cited; KB-018 is excluded | Retrieval precedence |
| Unsupported citations | Verify each citation is a selected current source | Before API response |
| Invented ticket IDs | Strip unconfirmed IDs unless `result.ticket_id` came from the Helpdesk API | Before API response |
| Unauthorized write | Stored, schema-valid draft plus `/api/approve` idempotency key | Approval code |

## 7. First 10 owned test cases

1. happy_path: cited NX-112 response then approved ticket.
2. clarification: vague VPN report asks only for error code/email.
3. conflict: KB-002 beats KB-001 and KB-018 for NX-781.
4. rejection: rejected draft writes no ticket.
5. tool_failure: API 503 returns no invented ticket ID.
6. injection: override/secret prompt is blocked before retrieval.
7. memory: requester memory survives a new session.
8. policy_conflict: Finance VPN routes to Security Operations.
9. guardrail: contractor VPN request routes to VDI without a ticket.
10. grounding: PDF-only printing content is cited.

## 8. Walking skeleton

`NX-112` → Intake & Safety → employee/status MCP reads → Resolution & Escalation → KB-002 cited
answer → ticket draft → explicit approval → MCP `create_ticket` → real `IT-` ID.

## 9. Risks and scope

OpenRouter availability and cost are the largest runtime risk. The deterministic safety and
retrieval layer remains available when the provider fails, but deployed agentic mode requires an
`OPENROUTER_API_KEY`. Video, public repository, team links, and class check-ins are human-owned
submission artifacts.
