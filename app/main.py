from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.approval import approve
from app.guardrails import enforce_output
from app.models import ApproveRequest, ChatRequest, ChatResponse
from app.retrieval.search import KnowledgeBase
from app.workflow import HelpdeskWorkflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.workflow = HelpdeskWorkflow(KnowledgeBase.load_or_build())
    yield


app = FastAPI(title="Nakhla IT Helpdesk Agent", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    email = str(request.user.email) if request.user and request.user.email else None
    response = await app.state.workflow.chat(request.session_id, request.message, email)
    return enforce_output(response, app.state.workflow.kb)


@app.post("/api/approve", response_model=ChatResponse)
async def approve_action(request: ApproveRequest) -> ChatResponse:
    response = await approve(request.session_id, request.action_id, request.approved)
    return enforce_output(response, app.state.workflow.kb)
