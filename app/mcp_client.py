from __future__ import annotations

import json
import os
import time
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import HELPDESK_MCP_ARGS, HELPDESK_MCP_COMMAND
from app.models import ToolCall


class HelpdeskMcpClient:
    """Short-lived MCP sessions keep state in the supplied simulator."""

    async def call(self, tool: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], ToolCall]:
        started = time.perf_counter()
        try:
            params = StdioServerParameters(
                command=HELPDESK_MCP_COMMAND,
                args=HELPDESK_MCP_ARGS,
                env=dict(os.environ),
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool, arguments)
            text = "".join(
                item.text for item in result.content if getattr(item, "type", None) == "text"
            )
            payload = json.loads(text) if text else {"ok": False, "error": {"code": "empty_response"}}
        except Exception as exc:
            payload = {"ok": False, "error": {"code": "mcp_error", "message": str(exc)}}
        elapsed = round((time.perf_counter() - started) * 1000)
        return payload, ToolCall(tool=tool, ok=bool(payload.get("ok")), ms=elapsed)

    async def lookup_employee(self, email: str) -> tuple[dict[str, Any], ToolCall]:
        return await self.call("lookup_employee", {"email": email})

    async def get_service_status(self) -> tuple[dict[str, Any], ToolCall]:
        return await self.call("get_service_status", {})

    async def create_ticket(self, draft: dict[str, Any], action_id: str) -> tuple[dict[str, Any], ToolCall]:
        return await self.call("create_ticket", {**draft, "idempotency_key": action_id})
