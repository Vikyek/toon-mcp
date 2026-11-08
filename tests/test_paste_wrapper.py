"""Tests for PTY bracketed-paste JSON-to-TOON wrapper."""

from __future__ import annotations

import json
import os
import pty
import select
import subprocess
import sys
import termios
import time

import pytest

from src.paste_wrapper import (
    BRACKETED_PASTE_END,
    BRACKETED_PASTE_START,
    BracketedPasteStreamProcessor,
    build_parser,
    toonify_text,
)
from src.toon_converter import convert_toon_to_json


SAMPLE_USERS = {
    "users": [
        {"id": 1, "name": "Alice Smith", "status": "active", "department": "engineering"},
        {"id": 2, "name": "Bob Jones", "status": "inactive", "department": "engineering"},
        {"id": 3, "name": "Carol Lee", "status": "active", "department": "operations"},
    ]
}


def test_toonify_pure_json_roundtrip_and_aggressive() -> None:
    raw = json.dumps(SAMPLE_USERS, indent=2)
    converted = toonify_text(raw, aggressive=True, min_chars=60)

    assert converted != raw
    assert len(converted) < len(raw)
    parsed = json.loads(converted)
    assert parsed["_toon"] == "1.0"
    assert "_custom_keys" in parsed  # aggressive abbreviated "department"
    assert json.loads(convert_toon_to_json(converted)) == SAMPLE_USERS


def test_toonify_preserves_cr_newlines_around_pure_json() -> None:
    raw = "\r" + json.dumps(SAMPLE_USERS, indent=2).replace("\n", "\r") + "\r"
    converted = toonify_text(raw, aggressive=True, min_chars=60)

    assert converted.startswith("\r{")
    assert converted.endswith("}\r")
    core = converted.strip("\r")
    assert json.loads(convert_toon_to_json(core)) == SAMPLE_USERS


def test_toonify_skips_small_or_non_shrinking_json() -> None:
    tiny = '{"a": 1}'
    assert toonify_text(tiny, min_chars=0) == tiny

    below_min = json.dumps({"id": 1, "name": "Jo", "status": "ok"})
    assert toonify_text(below_min, min_chars=60) == below_min


def test_toonify_skips_already_toon_pure_and_embedded() -> None:
    toon_payload = toonify_text(json.dumps(SAMPLE_USERS, indent=2), aggressive=True)
    assert toonify_text(toon_payload, min_chars=0) == toon_payload

    mixed = f"Already TOON:\n{toon_payload}\nKeep untouched."
    assert toonify_text(mixed, min_chars=0, embedded=True) == mixed


def test_toonify_embedded_mixed_text_and_code() -> None:
    payload_a = json.dumps(SAMPLE_USERS, indent=2)
    payload_b = json.dumps(
        [
            {"id": i, "name": f"Item {i}", "status": "ready", "enabled": True}
            for i in range(4)
        ],
        indent=2,
    )
    mixed = (
        "Check payload A:\n"
        f"```json\n{payload_a}\n```\n"
        "Ignore JS snippet: function f() { const x = {a: 1}; return x; }\n"
        "And payload B:\n"
        f"{payload_b}\n"
        "Done."
    )

    result = toonify_text(mixed, aggressive=True, min_chars=60, embedded=True)
    assert "function f() { const x = {a: 1}; return x; }" in result
    assert "```json\n{" in result
    assert result.count('"_toon":"1.0"') == 2
    assert len(result) < len(mixed)

    # --pure-only mode must leave mixed text unchanged
    assert toonify_text(mixed, aggressive=True, min_chars=60, embedded=False) == mixed


def test_stream_processor_chunked_markers_and_esc() -> None:
    proc = BracketedPasteStreamProcessor(
        lambda text: toonify_text(text, aggressive=True, min_chars=60)
    )

    # Normal text passes straight through
    assert proc.feed(b"hello ") == b"hello "
    assert not proc.has_pending_prefix()

    # Standalone Esc held briefly, then flushed on timeout
    assert proc.feed(b"\x1b") == b""
    assert proc.has_pending_prefix()
    assert proc.flush_pending() == b"\x1b"
    assert not proc.has_pending_prefix()

    # Arrow key (\x1b[A) flushes immediately without waiting
    assert proc.feed(b"\x1b") == b""
    assert proc.feed(b"[A") == b"\x1b[A"
    assert not proc.has_pending_prefix()

    # Split bracketed paste across arbitrary 1-2 byte chunks
    raw_json = json.dumps(SAMPLE_USERS, indent=2).encode("utf-8")
    stream = BRACKETED_PASTE_START + raw_json + BRACKETED_PASTE_END + b"tail"
    out = bytearray()
    for i in range(0, len(stream), 3):
        out.extend(proc.feed(stream[i : i + 3]))

    result_bytes = bytes(out)
    assert result_bytes.startswith(BRACKETED_PASTE_START)
    assert result_bytes.endswith(BRACKETED_PASTE_END + b"tail")
    inner = result_bytes[len(BRACKETED_PASTE_START) : -len(BRACKETED_PASTE_END + b"tail")]
    assert len(inner) < len(raw_json)
    assert json.loads(convert_toon_to_json(inner.decode("utf-8"))) == SAMPLE_USERS


def test_stream_processor_binary_and_overflow_safety() -> None:
    proc = BracketedPasteStreamProcessor(lambda s: s.upper(), max_paste_bytes=16)

    # Non-UTF-8 bytes pass through unaltered
    invalid_utf8 = b"\xff\xfe\xfd"
    out = proc.feed(BRACKETED_PASTE_START + invalid_utf8 + BRACKETED_PASTE_END)
    assert out == BRACKETED_PASTE_START + invalid_utf8 + BRACKETED_PASTE_END

    # Overflow triggers raw flush and resets paste state
    big = b"a" * 20
    first = proc.feed(BRACKETED_PASTE_START + big)
    assert first == BRACKETED_PASTE_START + big
    second = proc.feed(BRACKETED_PASTE_END + b"ok")
    assert second == BRACKETED_PASTE_END + b"ok"


def test_parser_remainder_and_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(["--no-aggressive", "--pure-only", "--min-chars", "120", "--", "agy", "-c"])
    assert args.no_aggressive is True
    assert args.pure_only is True
    assert args.min_chars == 120
    assert args.command == ["--", "agy", "-c"]


def test_cli_entrypoints_help_and_version() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env["PYTHONPATH"] = repo_root + (":" + env["PYTHONPATH"] if "PYTHONPATH" in env else "")

    for mod in ("src.server", "src.paste_wrapper"):
        res_help = subprocess.run(
            [sys.executable, "-m", mod, "--help"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res_help.returncode == 0
        assert "usage:" in res_help.stdout.lower()

        res_ver = subprocess.run(
            [sys.executable, "-m", mod, "--version"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res_ver.returncode == 0
        assert "1.0.0" in res_ver.stdout or "1.0.0" in res_ver.stderr


def _run_in_pty(cmd: list[str], paste_payload: bytes, extra_env: dict[str, str] | None = None) -> tuple[int, bytes]:
    """Spawn cmd inside an outer PTY, send bracketed paste, return (exitcode, child_output)."""
    master_fd, slave_fd = pty.openpty()
    attrs = termios.tcgetattr(slave_fd)
    # Raw-ish slave so outer PTY does not echo or translate control sequences
    attrs[3] &= ~(termios.ECHO | termios.ICANON)
    termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)

    env = os.environ.copy()
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env["PYTHONPATH"] = repo_root + (":" + env["PYTHONPATH"] if "PYTHONPATH" in env else "")
    if extra_env:
        env.update(extra_env)

    proc = subprocess.Popen(
        cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        start_new_session=True,
        env=env,
    )
    os.close(slave_fd)

    output = bytearray()
    sent = False
    deadline = time.monotonic() + 5.0
    try:
        while time.monotonic() < deadline:
            rlist, _, _ = select.select([master_fd], [], [], 0.1)
            if master_fd in rlist:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                output.extend(chunk)
                if not sent and b"READY" in output:
                    os.write(
                        master_fd,
                        BRACKETED_PASTE_START + paste_payload + BRACKETED_PASTE_END + b"\n",
                    )
                    sent = True
            elif proc.poll() is not None:
                break
        if proc.poll() is None:
            proc.kill()
        rc = proc.wait(timeout=2.0)
    finally:
        os.close(master_fd)
    return rc, bytes(output)


def test_pty_proxy_end_to_end_and_disable_env() -> None:
    child_code = (
        "import os, sys, tty, termios; "
        "fd = sys.stdin.fileno(); "
        "old = termios.tcgetattr(fd); "
        "tty.setraw(fd); "
        "sys.stdout.buffer.write(b'READY\\n'); "
        "sys.stdout.buffer.flush(); "
        "data = bytearray(); "
        "\nwhile not data.endswith(b'\\x1b[201~\\n'):\n"
        "    b = os.read(fd, 1)\n"
        "    if not b: break\n"
        "    data.extend(b)\n"
        "termios.tcsetattr(fd, termios.TCSADRAIN, old); "
        "sys.stdout.buffer.write(b'GOT:' + bytes(data)); "
        "sys.stdout.buffer.flush(); "
        "sys.exit(7)"
    )
    wrap_cmd = [
        sys.executable,
        "-m",
        "src.paste_wrapper",
        "--",
        sys.executable,
        "-c",
        child_code,
    ]
    raw_json = json.dumps(SAMPLE_USERS, indent=2).encode("utf-8")

    rc, out = _run_in_pty(wrap_cmd, raw_json)
    assert rc == 7
    assert b'GOT:\x1b[200~{"_toon":"1.0"' in out
    assert b"\x1b[201~" in out

    # Mixed text + embedded JSON through the real PTY proxy
    mixed_paste = b"Inspect this response:\n" + raw_json + b"\nWhat broke?"
    rc_mix, out_mix = _run_in_pty(wrap_cmd, mixed_paste)
    assert rc_mix == 7
    assert b'Inspect this response:' in out_mix
    assert b'{"_toon":"1.0"' in out_mix
    assert b"What broke?" in out_mix

    # Disabled via TOON_WRAP_DISABLE=1 passes original JSON untouched
    rc_off, out_off = _run_in_pty(wrap_cmd, raw_json, extra_env={"TOON_WRAP_DISABLE": "1"})
    assert rc_off == 7
    assert b'GOT:\x1b[200~{\r\n  "users":' in out_off or b'GOT:\x1b[200~{\n  "users":' in out_off
