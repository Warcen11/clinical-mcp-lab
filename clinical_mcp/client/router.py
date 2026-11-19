"""Three MCP transport connectors; every tool execution uses tools/call."""
from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import httpx2 as httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import PaginatedRequestParams

from clinical_mcp.client.tracing import PacketTrace, ReadTap, WriteTap
from clinical_mcp.client.validation import coerce

ROOT = Path(__file__).resolve().parents[2]
LOCAL_SSE_URL = "http://127.0.0.1:8000/sse"
REMOTE_URL = os.environ.get("CLINICAL_MCP_REMOTE_URL", "https://pubmed.caseyjhand.com/mcp")
SOURCES = {
    "stdio": "Локальный stdio",
    "sse": "Локальный SSE :8000",
    "remote": "Внешний PubMed (HTTP)",
}


def local_direct_http_client(headers=None, timeout=None, auth=None):
    """Bypass HTTP(S)_PROXY only for loopback SSE, keeping remote proxy support.

    MCP SDK 2.x calls this factory for GET /sse and subsequent POST /messages.
    """
    return httpx.AsyncClient(
        headers=headers, timeout=timeout, auth=auth, trust_env=False,
    )


@asynccontextmanager
async def connection(source: str):
    if source == "stdio":
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "clinical_mcp.stdio.server"],
            env={"PYTHONPATH": str(ROOT)},
        )
        context = stdio_client(params)
    elif source == "sse":
        context = sse_client(LOCAL_SSE_URL, httpx_client_factory=local_direct_http_client)
    elif source == "remote":
        if not REMOTE_URL.startswith("https://"):
            raise ValueError("Внешний MCP endpoint должен использовать HTTPS.")
        context = streamable_http_client(REMOTE_URL)
    else:
        raise ValueError(f"Неизвестный источник: {source}")
    trace = PacketTrace()
    async with context as streams:
        read, write = streams[:2]
        async with ClientSession(ReadTap(read, trace), WriteTap(write, trace)) as session:
            await session.initialize()  # Actual initialize, then tools/list and tools/call
            yield session, trace


async def _execute(source: str, tool_name: str | None, args: dict | None) -> dict:
    async with connection(source) as (session, trace):
        pages = []
        cursor = None
        for _ in range(20):
            result = await session.list_tools(
                params=PaginatedRequestParams(cursor=cursor) if cursor else None
            )
            pages.extend(result.tools)
            cursor = result.next_cursor
            if not cursor:
                break
        else:
            raise RuntimeError("Превышен лимит страниц tools/list")
        tools = [t.model_dump(by_alias=True, mode="json", exclude_none=True) for t in pages]
        data = None
        warnings = []
        if tool_name is not None:
            selected = next((t for t in tools if t["name"] == tool_name), None)
            if selected is None:
                raise ValueError(f"Инструмент «{tool_name}» отсутствует в tools/list")
            cleaned, warnings = coerce(selected.get("inputSchema", {}), args or {})
            response = await session.call_tool(tool_name, cleaned)
            data = response.model_dump(by_alias=True, mode="json", exclude_none=True)
        return {"tools": tools, "result": data, "trace": trace.events, "warnings": warnings}


def _connection_failure(exc: BaseException) -> bool:
    """Recognize transient connection errors, including nested async ExceptionGroups."""
    if isinstance(exc, BaseExceptionGroup):
        return bool(exc.exceptions) and all(_connection_failure(e) for e in exc.exceptions)
    return isinstance(exc, (OSError, ConnectionError, TimeoutError, anyio.BrokenResourceError,
                            anyio.ClosedResourceError, anyio.EndOfStream))


async def execute_async(source: str, tool_name: str | None = None, args: dict | None = None) -> dict:
    attempts = 3 if source == "sse" else 1
    for attempt in range(attempts):
        try:
            timeout = 12 if source == "remote" else 15
            with anyio.fail_after(timeout):
                return await _execute(source, tool_name, args)
        except Exception as exc:
            if not _connection_failure(exc):
                raise
            if attempt + 1 >= attempts:
                raise RuntimeError(f"MCP {source} недоступен ({exc})") from exc
            await asyncio.sleep(0.25 * (attempt + 1))
    raise RuntimeError("Попытки подключения исчерпаны")


def execute(source: str, tool_name: str | None = None, args: dict | None = None) -> dict:
    """Single UI-call boundary; each invocation owns a new complete async session."""
    return asyncio.run(execute_async(source, tool_name, args))
