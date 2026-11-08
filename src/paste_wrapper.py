"""
PTY bracketed-paste wrapper that automatically converts pasted JSON to TOON.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
import pty
import select
import signal
import sys
import termios
import tty
from typing import Any, Callable, Optional, Sequence

from . import __version__
from .toon_converter import convert_json_to_toon

BRACKETED_PASTE_START = b"\x1b[200~"
BRACKETED_PASTE_END = b"\x1b[201~"
DEFAULT_MIN_CHARS = 60
ESC_TIMEOUT_SEC = 0.025
MAX_PASTE_BYTES = 10 * 1024 * 1024  # 10 MiB safety cap


def _try_convert_json_obj(
    obj: Any,
    raw_slice: str,
    *,
    aggressive: bool,
    min_chars: int,
) -> Optional[str]:
    """Convert a parsed JSON object/array to TOON only if it saves characters."""
    if not isinstance(obj, (dict, list)):
        return None
    # Never double-encode payloads that are already in TOON format
    if isinstance(obj, dict) and "_toon" in obj:
        return None
    if len(raw_slice) < min_chars:
        return None

    try:
        toon_str = convert_json_to_toon(obj, aggressive=aggressive)
    except Exception:
        return None

    if len(toon_str) < len(raw_slice):
        return toon_str
    return None


def toonify_text(
    text: str,
    *,
    aggressive: bool = True,
    min_chars: int = DEFAULT_MIN_CHARS,
    embedded: bool = True,
) -> str:
    """
    Convert pure JSON or embedded JSON blocks inside pasted text into TOON.

    Leaves data untouched if parsing fails, the payload is already TOON,
    its length is below ``min_chars``, or TOON output is not shorter.
    """
    if not text:
        return text

    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            obj = None
        if obj is not None:
            lead_len = len(text) - len(text.lstrip())
            trail_len = len(text) - len(text.rstrip())
            end_idx = len(text) - trail_len if trail_len else len(text)
            raw_core = text[lead_len:end_idx]
            converted = _try_convert_json_obj(
                obj,
                raw_core,
                aggressive=aggressive,
                min_chars=min_chars,
            )
            if converted is None:
                return text
            return text[:lead_len] + converted + text[end_idx:]

    if not embedded:
        return text

    decoder = json.JSONDecoder()
    out: list[str] = []
    pos = 0
    last_emit = 0
    text_len = len(text)

    while pos < text_len:
        idx_obj = text.find("{", pos)
        idx_arr = text.find("[", pos)
        if idx_obj == -1 and idx_arr == -1:
            break
        if idx_obj == -1:
            cand = idx_arr
        elif idx_arr == -1:
            cand = idx_obj
        else:
            cand = idx_obj if idx_obj < idx_arr else idx_arr

        try:
            obj, end = decoder.raw_decode(text, cand)
        except json.JSONDecodeError:
            pos = cand + 1
            continue

        raw_slice = text[cand:end]
        converted = _try_convert_json_obj(
            obj,
            raw_slice,
            aggressive=aggressive,
            min_chars=min_chars,
        )
        if converted is not None:
            out.append(text[last_emit:cand])
            out.append(converted)
            last_emit = end
        # Advance past the entire valid JSON structure so inner nodes aren't re-processed
        pos = end

    if last_emit == 0:
        return text
    out.append(text[last_emit:])
    return "".join(out)


class BracketedPasteStreamProcessor:
    """Incremental byte-stream filter that rewrites bracketed-paste payloads."""

    def __init__(
        self,
        transform: Callable[[str], str],
        *,
        max_paste_bytes: int = MAX_PASTE_BYTES,
    ) -> None:
        self._transform = transform
        self._max_paste_bytes = max_paste_bytes
        self._in_paste = False
        self._pending = bytearray()
        self._paste_buf = bytearray()

    def has_pending_prefix(self) -> bool:
        """Return True if trailing bytes await completion of paste-start marker."""
        return not self._in_paste and bool(self._pending)

    def flush_pending(self) -> bytes:
        """Flush buffered escape prefix (e.g., standalone Esc keypress after timeout)."""
        if not self._pending:
            return b""
        flushed = bytes(self._pending)
        self._pending.clear()
        return flushed

    def feed(self, data: bytes) -> bytes:
        """Process an incoming byte chunk and return bytes ready to write downstream."""
        out = bytearray()
        cur = data

        while cur or (not self._in_paste and self._pending):
            if not self._in_paste:
                buf = bytes(self._pending) + cur
                self._pending.clear()
                cur = b""

                idx = buf.find(BRACKETED_PASTE_START)
                if idx != -1:
                    out.extend(buf[:idx])
                    self._in_paste = True
                    cur = buf[idx + len(BRACKETED_PASTE_START) :]
                    continue

                # Retain any trailing partial prefix of BRACKETED_PASTE_START
                max_k = min(len(buf), len(BRACKETED_PASTE_START) - 1)
                kept = 0
                for k in range(max_k, 0, -1):
                    if BRACKETED_PASTE_START.startswith(buf[-k:]):
                        self._pending.extend(buf[-k:])
                        kept = k
                        break
                out.extend(buf[: len(buf) - kept])
                break

            self._paste_buf.extend(cur)
            cur = b""

            end_idx = self._paste_buf.find(BRACKETED_PASTE_END)
            if end_idx != -1:
                raw_payload = bytes(self._paste_buf[:end_idx])
                remainder = bytes(self._paste_buf[end_idx + len(BRACKETED_PASTE_END) :])
                self._paste_buf.clear()
                self._in_paste = False

                try:
                    decoded = raw_payload.decode("utf-8")
                    transformed = self._transform(decoded).encode("utf-8")
                except UnicodeDecodeError:
                    transformed = raw_payload

                out.extend(BRACKETED_PASTE_START)
                out.extend(transformed)
                out.extend(BRACKETED_PASTE_END)
                cur = remainder
                continue

            if len(self._paste_buf) > self._max_paste_bytes:
                # Safety bailout: pass raw bytes through and exit paste mode
                out.extend(BRACKETED_PASTE_START)
                out.extend(self._paste_buf)
                self._paste_buf.clear()
                self._in_paste = False
                break

            break

        return bytes(out)


def _sync_winsize(src_fd: int, dst_fd: int) -> None:
    """Copy terminal window dimensions from src_fd to dst_fd."""
    try:
        winsize = fcntl.ioctl(src_fd, termios.TIOCGWINSZ, b"\x00" * 8)
        fcntl.ioctl(dst_fd, termios.TIOCSWINSZ, winsize)
    except OSError:
        pass


def run_pty_proxy(
    cmd: Sequence[str],
    processor: BracketedPasteStreamProcessor,
) -> int:
    """Run ``cmd`` inside a transparent PTY proxy that filters bracketed pastes."""
    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()

    if not (os.isatty(stdin_fd) and os.isatty(stdout_fd)):
        os.execvp(cmd[0], list(cmd))

    old_termios = termios.tcgetattr(stdin_fd)
    master_fd, slave_fd = pty.openpty()
    _sync_winsize(stdin_fd, slave_fd)

    winch_r, winch_w = os.pipe()
    os.set_blocking(winch_r, False)
    os.set_blocking(winch_w, False)

    pid = os.fork()
    if pid == 0:
        os.close(master_fd)
        os.close(winch_r)
        os.close(winch_w)
        os.setsid()
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        if slave_fd > 2:
            os.close(slave_fd)
        os.execvp(cmd[0], list(cmd))

    os.close(slave_fd)
    os.set_blocking(master_fd, False)

    def _on_winch(_signum: int, _frame: Any) -> None:
        try:
            os.write(winch_w, b"\x01")
        except OSError:
            pass

    prev_winch = signal.signal(signal.SIGWINCH, _on_winch)
    tty.setraw(stdin_fd, when=termios.TCSADRAIN)

    to_child = bytearray()
    to_stdout = bytearray()
    stdin_open = True
    child_open = True

    try:
        while child_open or to_stdout:
            rlist: list[int] = [winch_r]
            wlist: list[int] = []
            if stdin_open and child_open:
                rlist.append(stdin_fd)
            if child_open:
                rlist.append(master_fd)
            if to_child and child_open:
                wlist.append(master_fd)
            if to_stdout:
                wlist.append(stdout_fd)

            timeout = ESC_TIMEOUT_SEC if processor.has_pending_prefix() else None
            try:
                readable, writable, _ = select.select(rlist, wlist, [], timeout)
            except InterruptedError:
                continue

            if not readable and not writable and processor.has_pending_prefix():
                to_child.extend(processor.flush_pending())

            if winch_r in readable:
                try:
                    os.read(winch_r, 1024)
                except OSError:
                    pass
                _sync_winsize(stdin_fd, master_fd)

            if stdin_fd in readable:
                try:
                    chunk = os.read(stdin_fd, 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    stdin_open = False
                else:
                    to_child.extend(processor.feed(chunk))

            if master_fd in readable:
                try:
                    out_chunk = os.read(master_fd, 65536)
                except OSError as exc:
                    if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        out_chunk = None
                    else:
                        out_chunk = b""
                if out_chunk == b"":
                    child_open = False
                elif out_chunk:
                    to_stdout.extend(out_chunk)

            if master_fd in writable and to_child:
                try:
                    written = os.write(master_fd, to_child)
                    del to_child[:written]
                except OSError as exc:
                    if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                        child_open = False

            if stdout_fd in writable and to_stdout:
                try:
                    written = os.write(stdout_fd, to_stdout)
                    del to_stdout[:written]
                except OSError:
                    break
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_termios)
        signal.signal(signal.SIGWINCH, prev_winch)
        for fd in (master_fd, winch_r, winch_w):
            try:
                os.close(fd)
            except OSError:
                pass

    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser for ``toon-wrap``."""
    parser = argparse.ArgumentParser(
        prog="toon-wrap",
        description=(
            "Run an interactive CLI inside a PTY proxy that automatically converts "
            "pasted JSON (standalone or embedded) into compact TOON format."
        ),
    )
    parser.add_argument(
        "--no-aggressive",
        action="store_true",
        help="Disable aggressive domain-key auto-abbreviation (_custom_keys).",
    )
    parser.add_argument(
        "--pure-only",
        action="store_true",
        help="Convert only when the entire paste is valid JSON; ignore embedded blocks.",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=_env_int("TOON_WRAP_MIN_CHARS", DEFAULT_MIN_CHARS),
        help=f"Minimum JSON block length in chars to convert (default: {DEFAULT_MIN_CHARS}).",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command and arguments to run (optionally preceded by '--').",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point for ``toon-wrap``."""
    parser = build_parser()
    args = parser.parse_args(argv)

    cmd = list(args.command)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        parser.print_help(sys.stderr)
        return 2

    if os.environ.get("TOON_WRAP_DISABLE") == "1":
        os.execvp(cmd[0], cmd)

    aggressive = not args.no_aggressive
    embedded = not args.pure_only
    min_chars = max(0, args.min_chars)

    processor = BracketedPasteStreamProcessor(
        lambda text: toonify_text(
            text,
            aggressive=aggressive,
            min_chars=min_chars,
            embedded=embedded,
        )
    )
    return run_pty_proxy(cmd, processor)


if __name__ == "__main__":
    sys.exit(main())
