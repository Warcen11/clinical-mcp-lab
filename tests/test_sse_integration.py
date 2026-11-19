"""Optional real SSE test: run with RUN_SSE_INTEGRATION=1 python -m pytest -q."""
import os
import socket
import subprocess
import sys
import time

import pytest

if not os.environ.get("RUN_SSE_INTEGRATION"):
    pytest.skip("SSE integration is opt-in: RUN_SSE_INTEGRATION=1", allow_module_level=True)
pytest.importorskip("mcp")

from clinical_mcp.client.router import execute


def _wait_for_port(host: str, port: int, timeout: float = 8) -> bool:
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        with socket.socket() as sock:
            sock.settimeout(0.3)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.1)
    return False


def test_real_sse_mcp_connection():
    process = subprocess.Popen([sys.executable, "-m", "clinical_mcp.network.server"])
    try:
        assert _wait_for_port("127.0.0.1", 8000), "SSE server did not start"
        result = execute("sse", "critical_gcs", {"eye": 4, "verbal": 5, "motor": 6})
        assert len(result["tools"]) >= 5
        assert not result["result"].get("isError")
        assert any(e["packet"].get("method") == "tools/call"
                   for e in result["trace"] if isinstance(e["packet"], dict))

        # The two values satisfy their individual JSON Schema ranges, so the
        # client sanitizer lets them reach the server. The clinical relation
        # diastolic < systolic must be validated by the MCP tool itself.
        bad = execute("sse", "cardio_map", {"systolic": 100, "diastolic": 120})
        assert bad["result"] is not None
        assert bad["result"].get("isError") is True, bad["result"]
        assert any(e["packet"].get("method") == "tools/call"
                   for e in bad["trace"] if isinstance(e["packet"], dict))
        # A correct call still works after the server returns a ToolError.
        recovered = execute("sse", "cardio_map", {"systolic": 120, "diastolic": 80})
        assert not recovered["result"].get("isError"), recovered["result"]
    finally:
        process.terminate()
        process.wait(timeout=5)
