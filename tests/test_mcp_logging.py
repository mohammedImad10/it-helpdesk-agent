import json
import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.mcp_client import HelpdeskMcpClient


@pytest.mark.asyncio
async def test_successful_mcp_call_emits_structured_log(monkeypatch, caplog) -> None:
    @asynccontextmanager
    async def successful_stdio_client(_params):
        yield object(), object()

    class SuccessfulSession:
        def __init__(self, _read, _write):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, _type, _value, _traceback):
            return False

        async def initialize(self):
            return None

        async def call_tool(self, _tool, _arguments):
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text='{"ok": true}')]
            )

    monkeypatch.setattr("app.mcp_client.stdio_client", successful_stdio_client)
    monkeypatch.setattr("app.mcp_client.ClientSession", SuccessfulSession)
    caplog.set_level(logging.INFO, logger="app.mcp_client")

    payload, trace = await HelpdeskMcpClient().call("get_service_status", {})

    assert payload == {"ok": True}
    assert trace.ok is True
    assert json.loads(caplog.records[-1].message)["error_code"] is None
    assert json.loads(caplog.records[-1].message)["ok"] is True


@pytest.mark.asyncio
async def test_failed_mcp_call_emits_sanitized_structured_log(monkeypatch, caplog) -> None:
    @asynccontextmanager
    async def failing_stdio_client(_params):
        raise RuntimeError("connection failed for private@example.test")
        yield

    monkeypatch.setattr("app.mcp_client.stdio_client", failing_stdio_client)
    caplog.set_level(logging.INFO, logger="app.mcp_client")

    payload, trace = await HelpdeskMcpClient().call(
        "lookup_employee",
        {"email": "private@example.test"},
    )

    assert payload["error"]["code"] == "mcp_error"
    assert trace.ok is False
    log = json.loads(caplog.records[-1].message)
    assert log == {
        "error_code": "mcp_error",
        "event": "mcp_tool_call",
        "latency_ms": log["latency_ms"],
        "ok": False,
        "tool": "lookup_employee",
    }
    assert "private@example.test" not in caplog.text
