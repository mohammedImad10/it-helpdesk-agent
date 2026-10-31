# IT Helpdesk Agent Architecture

This diagram explains how a user message becomes a safe helpdesk response, and why ticket
creation is kept separate from normal chat.

![IT Helpdesk Agent architecture overview](architecture-overview.svg)

The top lane is the safe **chat path**. The bottom lane is the separate **approval-only ticket
write path**. Red arrows are the only path that can create a ticket.

| Diagram color | Meaning |
|---|---|
| Blue | Application/UI boundary |
| Green | Safety controls |
| Purple | Persistent state and retrieval data |
| Orange | External providers and simulator |
| Red | Approval-gated ticket-write boundary |

## What each part does

| Component | Responsibility |
|---|---|
| **Gradio UI** | Sends the selected employee identity, chat message, and approval decision to FastAPI. |
| **FastAPI** | Provides the two public routes: `/api/chat` and `/api/approve`. |
| **Input guard** | Blocks prompt injection and credential/secret requests before any MCP, retrieval, or LLM call. |
| **SQLite** | Persists session context, follow-up state, server-side drafts, and requester memory. |
| **MCP tools** | Read verified employee, incident, and ticket data; create a ticket only from the approval path. |
| **Chroma** | Stores KB section vectors, source paths, and document-control metadata for semantic retrieval. |
| **LangGraph** | Runs Intake and Safety, then Resolution and Escalation, to produce structured routing decisions. |
| **Python policy** | Applies precedence, department rules, incident handling, validation, and approval constraints. |
| **Output guard** | Allows only current citations and ticket IDs returned by the Helpdesk API. |

## Two separate paths

### 1. Normal chat path

```mermaid
flowchart LR
    A[Message] --> B[Input guard]
    B --> C[Session and employee context]
    C --> D[MCP status and ticket reads]
    D --> E[Chroma retrieval]
    E --> F[LangGraph routing]
    F --> G[Python policy and response]
    G --> H[Output guard]
    H --> I[Reply with citations]
```

This path can answer, ask for missing context, offer escalation, report an active incident, or
prepare a draft. It **cannot create a ticket**.

### 2. Ticket-write path

```mermaid
flowchart LR
    A[User sees ticket draft] --> B{User approves?}
    B -->|Reject| C[Consume action<br/>No ticket written]
    B -->|Approve| D[Load server-stored TicketDraft]
    D --> E[MCP create_ticket<br/>with idempotency key]
    E -->|Failure| F[Keep draft for retry<br/>No ticket ID]
    E -->|Confirmed| G[Save requester memory<br/>Return real IT-#### ID]
```

The browser never supplies ticket fields for creation. It sends only the stored `action_id` and
an approval decision. This keeps the approval gate enforceable even if a model, user message, or
retrieved document is untrusted.

## Key safety rule

**LangGraph and OpenRouter decide the support route; Python decides what is allowed to happen.**

The LLM roles cannot call MCP tools, create tickets, bypass source precedence, invent citations,
or approve a write.
