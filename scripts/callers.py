#!/usr/bin/env python3
"""Answer "who calls this symbol" from pyright's own call hierarchy.

`just typecheck` already resolves every `service: ProfileService = Depends(...)`
receiver in this codebase. This asks that same server one more question instead
of building a second index: one hop, exact call sites, and nothing that can go
stale between two commits.

    just callers app/kernel/llm/profiles.py ordered
    just callers app/kernel/llm/profiles.py:26

Exact positions matter more than breadth here — a text search for `.create(`
finds ten call sites in this repo and no way to tell which receiver they hit.
"""

from __future__ import annotations

import json
import queue
import re
import shutil
import subprocess  # nosec B404 - controlled pyright-langserver invocation, no shell
import sys
import threading
import time
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, TypedDict, cast
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent

KIND_NAMES = {
    5: "class",
    6: "method",
    7: "property",
    8: "field",
    9: "constructor",
    12: "function",
    13: "variable",
}


class Position(TypedDict):
    line: int
    character: int


class CallRange(TypedDict):
    start: Position


class Origin(TypedDict, total=False):
    """The caller pyright names, and where inside it the call sits."""

    uri: str
    name: str
    selectionRange: CallRange


class CallHierarchyItem(TypedDict):
    name: str
    kind: int
    uri: str


# `from` is a Python keyword, so the shape needs the functional syntax.
IncomingCall = TypedDict(
    "IncomingCall", {"from": Origin, "fromRanges": list[CallRange]}, total=False
)


@dataclass(frozen=True)
class CallSite:
    path: str
    line: int
    enclosing: str

    @property
    def is_test(self) -> bool:
        """Classify callers by test directories or the test file prefix."""
        parts = self.path.split("/")
        return "tests" in parts or "e2e" in parts or Path(self.path).name.startswith("test_")


class LanguageServer:
    """The slice of LSP this needs: framing, one request, one response."""

    def __init__(self, command: list[str], cwd: Path) -> None:
        """Start the server and read its framed output on a background thread."""
        self._proc = subprocess.Popen(  # noqa: S603  # nosec  # fixed argv, no shell
            command,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._messages: queue.Queue[dict[str, Any] | None] = queue.Queue()
        # The last stderr lines are the only explanation a crash leaves behind.
        self._stderr: deque[str] = deque(maxlen=8)
        self._next_id = 1
        stdout, stderr = self._proc.stdout, self._proc.stderr
        if stdout is None or stderr is None:  # pragma: no cover - Popen guarantees both
            raise RuntimeError("pyright-langserver has no pipes")
        self._threads = [
            threading.Thread(target=self._read, args=(stdout,), daemon=True),
            threading.Thread(target=self._drain_stderr, args=(stderr,), daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def _drain_stderr(self, stream: IO[bytes]) -> None:
        """Keep the tail of whatever the server complained about."""
        for line in stream:
            text = line.decode(errors="replace").strip()
            if text:
                self._stderr.append(text)

    def _failure(self, method: str) -> RuntimeError:
        """Name the exit, not a timeout: a dead server and a slow one differ."""
        code = self._proc.poll()
        cause = " | ".join(self._stderr) or "nothing on stderr"
        return RuntimeError(
            f"pyright-langserver closed its output before answering {method} "
            f"(exit code {code}: {cause})"
        )

    def _read(self, stream: IO[bytes]) -> None:
        """Signal the end of server output even when frame parsing fails."""
        try:
            self._read_frames(stream)
        finally:
            self._messages.put(None)

    def _read_frames(self, stream: IO[bytes]) -> None:
        """Queue decoded LSP messages until EOF or an incomplete frame."""
        while True:
            length: int | None = None
            while True:
                header = stream.readline()
                if not header:
                    return
                if header in (b"\r\n", b"\n"):
                    break
                if header.lower().startswith(b"content-length:"):
                    length = int(header.split(b":", 1)[1])
            if length is None:
                continue
            body = stream.read(length)
            if len(body) != length:
                return
            try:
                self._messages.put(json.loads(body))
            except json.JSONDecodeError:
                continue

    def _send(self, message: dict[str, Any]) -> None:
        """Write and flush one JSON-RPC message with its LSP length header."""
        body = json.dumps(message).encode()
        stdin = self._proc.stdin
        if stdin is None:  # pragma: no cover - Popen above guarantees it
            raise RuntimeError("pyright-langserver has no stdin")
        try:
            stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
            stdin.flush()
        except BrokenPipeError:
            raise self._failure(str(message.get("method", "?"))) from None

    def notify(self, method: str, params: dict[str, Any]) -> None:
        """Send a notification that does not expect a response."""
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def request(self, method: str, params: dict[str, Any], timeout: float) -> object:
        """Wait for this request's response, failing on server EOF or timeout."""
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"pyright did not answer {method} within {timeout:.0f}s")
            try:
                message = self._messages.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(
                    f"pyright did not answer {method} within {timeout:.0f}s"
                ) from None
            if message is None:
                raise self._failure(method)
            if message.get("id") != request_id:
                continue
            error = message.get("error")
            if error:
                raise RuntimeError(str(error.get("message", error)))
            return message.get("result")

    def close(self) -> None:
        """Terminate and reap the language server, then release its pipes."""
        if self._proc.poll() is None:
            self._proc.kill()
        self._proc.wait(timeout=5)
        # The readers own the pipes; joining them first keeps interpreter
        # shutdown from finalising a file another thread still reads.
        for thread in self._threads:
            thread.join(timeout=2)
        for stream in (self._proc.stdin, self._proc.stdout, self._proc.stderr):
            if stream is not None:
                with suppress(BrokenPipeError):
                    stream.close()


def find_symbol(source: list[str], name: str) -> int:
    """Return the 0-based line of `def name` or `class name`."""
    pattern = re.compile(rf"^\s*(?:async\s+)?(?:def|class)\s+{re.escape(name)}\b")
    for index, line in enumerate(source):
        if pattern.match(line):
            return index
    declared: list[str] = []
    for line in source:
        match = re.match(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", line)
        if match:
            declared.append(match.group(1))
    hint = ", ".join(sorted(set(declared))[:12]) or "none"
    raise LookupError(f"{name} is not defined in this file. Top-level names: {hint}")


def position_for(source: list[str], line_index: int, name: str) -> dict[str, int]:
    """Place the cursor inside the symbol's own name, not at the indentation."""
    line = source[line_index]
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    match = pattern.search(line)
    return {
        "line": line_index,
        "character": match.start() if match else len(line) - len(line.lstrip()),
    }


def collect_calls(result: list[IncomingCall] | None) -> list[CallSite]:
    """Normalize incoming call ranges into unique, sorted, 1-based call sites.

    Pyright answers `null` instead of an empty list for files outside its
    workspace, so an absent answer is a legitimate "no callers".
    """
    sites: list[CallSite] = []
    for call in result or []:
        origin = call.get("from")
        if origin is None:
            continue
        uri = origin.get("uri", "")
        path = unquote(uri.removeprefix("file://"))
        relative = str(Path(path).relative_to(ROOT)) if path.startswith(str(ROOT)) else path
        ranges = call.get("fromRanges")
        if not ranges:
            selection = origin.get("selectionRange")
            ranges = [selection] if selection is not None else []
        for call_range in ranges:
            start = call_range.get("start", {"line": 0, "character": 0})
            sites.append(
                CallSite(
                    path=relative,
                    line=start["line"] + 1,
                    enclosing=origin.get("name") or "<module>",
                )
            )
    # pyright reports the same site once per incoming-call record it builds.
    return sorted(set(sites), key=lambda site: (site.path, site.line))


def _resolve_server() -> list[str]:
    """Find the pinned environment's language server, falling back to PATH."""
    candidate = Path(sys.executable).with_name("pyright-langserver")
    if candidate.exists():
        return [str(candidate), "--stdio"]
    found = shutil.which("pyright-langserver")
    if found:
        return [found, "--stdio"]
    raise FileNotFoundError(
        "pyright-langserver is not installed. It ships with the pinned pyright: `uv sync`."
    )


def symbol_on_line(source: list[str], line_index: int) -> str:
    """The name a `path:line` target points at — not the first word on the line.

    `async def ordered(...)` starts with `async`, so anything that takes the first
    identifier asks pyright about a symbol that does not exist, and the answer is
    a silent "no declaration found" instead of the caller list.
    """
    declared = re.search(r"(?:def|class)\s+(\w+)", source[line_index])
    return declared.group(1) if declared else ""


def parse_target(argv: list[str]) -> tuple[Path, str, int | None]:
    """Resolve a file target with an optional symbol and inline line number."""
    if not argv or len(argv) > 2:
        surplus = f"; drop {argv[2:]!r}" if len(argv) > 2 else ""
        raise ValueError(f"usage: callers <path.py> <symbol>  |  callers <path.py:line>{surplus}")
    target = argv[0]
    inline_line = None
    if ":" in target and target.rsplit(":", 1)[1].isdigit():
        target, suffix = target.rsplit(":", 1)
        inline_line = int(suffix)
    path = Path(target)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"{target} does not exist")
    symbol = argv[1] if len(argv) > 1 else ""
    if not symbol and inline_line is None:
        raise ValueError("pass a symbol name or an explicit path:line")
    return path, symbol, inline_line


def main(argv: list[str]) -> int:
    """Resolve a target, query Pyright, and print production and test callers."""
    try:
        path, symbol, inline_line = parse_target(argv)
    except (ValueError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    source = path.read_text(encoding="utf-8").splitlines()
    try:
        if inline_line is not None:
            line_index = inline_line - 1
            symbol = symbol or symbol_on_line(source, line_index)
            if not symbol:
                raise LookupError(
                    f"no declaration on {path.name}:{inline_line}; pass the symbol name"
                )
        else:
            line_index = find_symbol(source, symbol)
    except (LookupError, IndexError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    uri = path.as_uri()
    server: LanguageServer | None = None
    try:
        server = LanguageServer(_resolve_server(), cwd=ROOT)
        server.request(
            "initialize",
            {
                "processId": None,
                "rootUri": ROOT.as_uri(),
                "capabilities": {"textDocument": {"callHierarchy": {"dynamicRegistration": False}}},
                "workspaceFolders": [{"uri": ROOT.as_uri(), "name": ROOT.name}],
            },
            timeout=120,
        )
        server.notify("initialized", {})
        server.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": "python",
                    "version": 1,
                    "text": "\n".join(source),
                }
            },
        )
        position = position_for(source, line_index, symbol)
        items = cast(
            "list[CallHierarchyItem]",
            server.request(
                "textDocument/prepareCallHierarchy",
                {"textDocument": {"uri": uri}, "position": position},
                timeout=120,
            ),
        )
        if not items:
            print(
                f"error: pyright found no declaration at {path.name}:{line_index + 1}",
                file=sys.stderr,
            )
            return 1
        item = items[0]
        calls = cast(
            "list[IncomingCall]",
            server.request("callHierarchy/incomingCalls", {"item": item}, timeout=120),
        )
    except (OSError, RuntimeError, TimeoutError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    finally:
        if server is not None:
            server.close()

    relative = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    kind = KIND_NAMES.get(int(item.get("kind", 0)), "symbol")
    sites = collect_calls(calls)
    production = [site for site in sites if not site.is_test]
    tests = [site for site in sites if site.is_test]

    print(f"{symbol} — {relative}:{line_index + 1} ({kind})")
    if not sites:
        print("0 callers.")
        return 0
    print(f"{len(sites)} callers: {len(production)} production, {len(tests)} test")
    for label, group in (("production", production), ("test", tests)):
        if not group:
            continue
        print(f"\n{label}")
        for site in group:
            print(f"  {site.path}:{site.line}  {site.enclosing or '<module>'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
