"""Requires the actual mcp 2.3 SDK. Integration tests don't use a fake RPC server."""
import pytest

pytest.importorskip("mcp")

from clinical_mcp.client.router import execute_async


@pytest.mark.asyncio
async def test_stdio_tool_list_and_call_over_real_mcp():
    data = await execute_async("stdio", "bmi", {"weight_kg": 80, "height_cm": 180})
    names = {tool["name"] for tool in data["tools"]}
    assert {"bmi", "gcs", "creatinine_clearance", "list_calculators"} <= names
    assert data["result"] is not None
    assert not data["result"].get("isError")
    assert any(e["packet"].get("method") == "tools/call"
               for e in data["trace"] if isinstance(e["packet"], dict))
    assert any(e["packet"].get("method") == "initialize"
               for e in data["trace"] if isinstance(e["packet"], dict))


@pytest.mark.asyncio
async def test_valid_gcs_over_real_stdio_mcp():
    # This is a success-path integration test; it must not claim to test errors.
    data = await execute_async("stdio", "gcs", {"eye": 4, "verbal": 5, "motor": 6})
    assert not data["result"].get("isError")
    assert any(e["packet"].get("method") == "tools/call"
               for e in data["trace"] if isinstance(e["packet"], dict))
