"""
MCP server integration tests via JSON-RPC (NDJSON) over stdio.
Tests the wire protocol directly against a subprocess server.
mcp>=1.0 uses newline-delimited JSON (one JSON object per line), not Content-Length framing.

These tests are marked `integration` and excluded from the in-container unit test run
(where pytest-asyncio's event loop interferes with blocking subprocess I/O):

    pytest tests/test_conversions.py          # unit tests only (runs in Docker)
    pytest -m integration                     # wire-protocol tests (run locally)
    pytest                                    # everything locally
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

# All tests in this file are integration tests; skip inside Docker
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# MCP NDJSON wire helpers
# ---------------------------------------------------------------------------

def _send(proc, msg: dict) -> None:
    """Write one JSON object as a single line to the server's stdin."""
    proc.stdin.write((json.dumps(msg) + "\n").encode())
    proc.stdin.flush()


def _read_one(proc, timeout: float = 5.0) -> dict | None:
    """
    Read one newline-delimited JSON message from the server's stdout.
    Skips notifications (no 'id' field); returns the first response or
    notification that matches (based on caller expectation).
    Returns None on timeout.
    """
    import select
    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        remaining = deadline - time.time()
        r, _, _ = select.select([proc.stdout], [], [], min(remaining, 0.2))
        if r:
            chunk = proc.stdout.read1(4096)  # non-blocking read
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if line:
                    return json.loads(line)
    return None


def _rpc(proc, id_: int, method: str, params: dict | None = None,
         skip_notifications: bool = True) -> dict:
    """Send a JSON-RPC request and return the response (skipping notifications)."""
    msg = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        msg["params"] = params
    _send(proc, msg)

    deadline = time.time() + 10.0
    while time.time() < deadline:
        resp = _read_one(proc, timeout=max(0.1, deadline - time.time()))
        if resp is None:
            raise TimeoutError(f"Timed out waiting for response to '{method}'")
        # If it's a notification (no 'id'), skip if requested
        if skip_notifications and "id" not in resp:
            continue
        return resp
    raise TimeoutError(f"No response received for '{method}'")


def _notify(proc, method: str, params: dict | None = None) -> None:
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    _send(proc, msg)


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

def start_server() -> subprocess.Popen:
    repo_root = Path(__file__).parent.parent
    return subprocess.Popen(
        [sys.executable, "-m", "src.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(repo_root),
    )


def initialize(proc) -> dict:
    """Perform the MCP handshake. Returns server capabilities."""
    resp = _rpc(proc, 1, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "pytest-integration", "version": "1.0"},
    })
    assert "result" in resp, f"initialize failed: {resp}"
    _notify(proc, "notifications/initialized")
    time.sleep(0.1)  # give the server a moment to process the notification
    return resp["result"]


def call_tool(proc, id_: int, name: str, arguments: dict) -> dict:
    """Call an MCP tool and return the parsed result content as a dict."""
    resp = _rpc(proc, id_, "tools/call", {"name": name, "arguments": arguments})
    assert "result" in resp, f"Tool '{name}' returned error: {resp}"
    content = resp["result"]["content"]
    assert len(content) > 0, f"Tool '{name}' returned empty content"
    return json.loads(content[0]["text"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMCPIntegration:
    """Full MCP wire-protocol integration tests using NDJSON framing."""

    _proc: subprocess.Popen | None = None

    @classmethod
    def setup_class(cls):
        cls._proc = start_server()
        time.sleep(0.5)
        caps = initialize(cls._proc)
        # accept either old or new capability shapes
        assert caps, f"Empty initialize response: {caps}"

    @classmethod
    def teardown_class(cls):
        if cls._proc:
            try:
                cls._proc.stdin.close()
            except Exception:
                pass
            try:
                cls._proc.wait(timeout=5)
            except Exception:
                cls._proc.kill()

    # --- convert_to_toon -----------------------------------------------

    def test_convert_to_toon_basic(self):
        data = {"id": 1, "name": "Alice", "status": "active"}
        result = call_tool(self._proc, 10, "convert_to_toon", {
            "json_data": json.dumps(data),
        })
        assert "toon_format" in result, result
        assert "savings" in result
        toon = json.loads(result["toon_format"])
        assert toon["_toon"] == "1.0"
        assert "d" in toon

    def test_convert_to_toon_key_abbreviation(self):
        data = {
            "id": 99, "name": "Bob", "status": "inactive",
            "metadata": {"created_at": "2025-01-01"}
        }
        result = call_tool(self._proc, 11, "convert_to_toon", {"json_data": json.dumps(data)})
        toon = json.loads(result["toon_format"])
        d = toon["d"]
        assert "i" in d       # id → i
        assert "n" in d       # name → n
        assert "s" in d       # status → s
        assert "meta" in d    # metadata → meta

    def test_convert_to_toon_savings_fields(self):
        # Use a larger object so savings are positive (tiny objects can be larger in TOON
        # due to the fixed {"_toon":"1.0","d":{}} envelope overhead)
        data = [
            {"id": i, "name": f"User {i}", "status": "active", "metadata": {"created_at": "2025-01-01"}}
            for i in range(10)
        ]
        result = call_tool(self._proc, 12, "convert_to_toon", {"json_data": json.dumps(data)})
        s = result["savings"]
        for field in ("original_chars", "toon_chars", "original_tokens",
                      "toon_tokens", "tokens_saved", "savings_percent", "compression_ratio"):
            assert field in s, f"Missing savings field: {field}"
        assert s["toon_chars"] < s["original_chars"]
        assert s["tokens_saved"] > 0

    def test_convert_to_toon_aggressive(self):
        data = [
            {"customer_first_name": f"First{i}", "customer_last_name": f"Last{i}", "active": True}
            for i in range(10)
        ]
        result = call_tool(self._proc, 13, "convert_to_toon", {
            "json_data": json.dumps(data),
            "aggressive": True,
        })
        toon = json.loads(result["toon_format"])
        assert "_custom_keys" in toon, "Aggressive mode should emit _custom_keys"
        assert len(toon["_custom_keys"]) > 0

    def test_convert_to_toon_schema_compression(self):
        data = [{"id": i, "name": f"Item {i}", "value": i * 10} for i in range(20)]
        result = call_tool(self._proc, 14, "convert_to_toon", {"json_data": json.dumps(data)})
        assert result["savings"]["savings_percent"] > 20

    # --- convert_to_json -----------------------------------------------

    def test_convert_to_json_round_trip(self):
        original = {
            "id": 42, "name": "Round Trip", "status": "active",
            "metadata": {"created_at": "2025-01-01"},
        }
        toon_result = call_tool(self._proc, 20, "convert_to_toon", {"json_data": json.dumps(original)})
        toon_str = toon_result["toon_format"]

        resp = _rpc(self._proc, 21, "tools/call", {
            "name": "convert_to_json",
            "arguments": {"toon_data": toon_str},
        })
        assert "result" in resp
        restored = json.loads(resp["result"]["content"][0]["text"])
        assert restored == original

    def test_convert_to_json_null_and_bool(self):
        original = {"value": None, "enabled": True, "disabled": False}
        toon_result = call_tool(self._proc, 22, "convert_to_toon", {"json_data": json.dumps(original)})
        resp = _rpc(self._proc, 23, "tools/call", {
            "name": "convert_to_json",
            "arguments": {"toon_data": toon_result["toon_format"]},
        })
        restored = json.loads(resp["result"]["content"][0]["text"])
        assert restored["value"] is None
        assert restored["enabled"] is True
        assert restored["disabled"] is False

    # --- analyze_patterns ----------------------------------------------

    def test_analyze_patterns_consistent_schema(self):
        data = [{"id": i, "name": f"Item {i}", "type": "product"} for i in range(10)]
        result = call_tool(self._proc, 30, "analyze_patterns", {"json_data": json.dumps(data)})
        assert "patterns" in result
        assert "recommendations" in result
        types = [p["type"] for p in result["patterns"]]
        assert any("schema" in t for t in types), f"No schema pattern in: {types}"

    def test_analyze_patterns_api_response(self):
        data = {"status": "success", "data": {"id": 1}, "message": "OK", "meta": {"page": 1}}
        result = call_tool(self._proc, 31, "analyze_patterns", {"json_data": json.dumps(data)})
        types = [p["type"] for p in result["patterns"]]
        assert "api_response" in types

    def test_analyze_patterns_has_recommendations(self):
        data = [{"id": i, "name": f"User {i}", "email": f"u{i}@ex.com"} for i in range(15)]
        result = call_tool(self._proc, 32, "analyze_patterns", {"json_data": json.dumps(data)})
        assert len(result["recommendations"]) > 0

    # --- get_compression_strategy --------------------------------------

    def test_get_compression_strategy_structure(self):
        data = [{"id": i, "name": f"Item {i}"} for i in range(20)]
        result = call_tool(self._proc, 40, "get_compression_strategy", {"json_data": json.dumps(data)})
        for field in ("use_schema_compression", "use_reference_compression",
                      "expected_savings_percent", "detected_patterns"):
            assert field in result, f"Missing field: {field}"
        assert result["expected_savings_percent"] > 0
        assert result["use_schema_compression"] is True

    def test_get_compression_strategy_single_object(self):
        data = {"id": 1, "name": "Test"}
        result = call_tool(self._proc, 41, "get_compression_strategy", {"json_data": json.dumps(data)})
        assert result["use_schema_compression"] is False

    # --- calculate_savings ---------------------------------------------

    def test_calculate_savings_fields(self):
        data = [{"id": i, "name": f"Item {i}", "status": "active"} for i in range(50)]
        result = call_tool(self._proc, 50, "calculate_savings", {"json_data": json.dumps(data)})
        for field in ("original_chars", "toon_chars", "original_tokens",
                      "toon_tokens", "tokens_saved", "savings_percent", "compression_ratio"):
            assert field in result, f"Missing field: {field}"
        assert result["savings_percent"] > 20

    def test_calculate_savings_token_math(self):
        data = {"id": 1, "name": "Test", "status": "active"}
        result = call_tool(self._proc, 51, "calculate_savings", {"json_data": json.dumps(data)})
        assert result["original_tokens"] == max(1, result["original_chars"] // 4)
        assert result["toon_tokens"] == max(1, result["toon_chars"] // 4)

    # --- batch_convert -------------------------------------------------

    def test_batch_convert_basic(self):
        items = [{"id": i, "name": f"Item {i}", "status": "active"} for i in range(5)]
        result = call_tool(self._proc, 60, "batch_convert", {"json_array": json.dumps(items)})
        assert result["converted_count"] == 5
        assert len(result["results"]) == 5
        for r in result["results"]:
            assert "toon" in r
            assert "savings_percent" in r

    def test_batch_convert_aggressive(self):
        items = [
            {"customer_first_name": f"First{i}", "customer_last_name": f"Last{i}"}
            for i in range(5)
        ]
        result = call_tool(self._proc, 61, "batch_convert", {
            "json_array": json.dumps(items),
            "aggressive": True,
        })
        assert result["converted_count"] == 5
        for r in result["results"]:
            toon = json.loads(r["toon"])
            assert "_toon" in toon

    # --- Error handling ------------------------------------------------

    def test_invalid_json_returns_error(self):
        resp = _rpc(self._proc, 70, "tools/call", {
            "name": "convert_to_toon",
            "arguments": {"json_data": "not valid json {{{"},
        })
        assert "result" in resp
        text = resp["result"]["content"][0]["text"]
        assert "Error" in text or "error" in text

    def test_unknown_tool_returns_error(self):
        resp = _rpc(self._proc, 71, "tools/call", {
            "name": "nonexistent_tool",
            "arguments": {},
        })
        has_error = (
            "error" in resp
            or ("result" in resp and "Error" in resp["result"]["content"][0]["text"])
        )
        assert has_error
