"""SSE parsing for the benchmark runner — line parser + typed collector.

Implements the parser contract from the verified API map
(``benchmark/docs/api-surface.md`` §6). Both documented stream flavors are
supported:

- **Flavor A** — data-only frames carrying raw item payloads, in-band
  error frames ``{"error": <str>, "code": "NOT_FOUND"|"CONFIG_ERROR"|"INTERNAL"}``,
  terminated by the literal sentinel frame ``data: [DONE]``.
- **Flavor B** — ``CoreferenceStreamEvent`` envelopes discriminated by the
  in-band JSON ``event`` key (``progress``|``result``|``done``|``error``)
  with ``is_final``; extra top-level keys (``x_trace_id``/``x_span_id``
  from ``observability.enrich_sse_data``) are tolerated.

Layering: ``parse_frames`` is the pure line-parser core (SSE field
semantics: comments, multi-line ``data`` join, optional ``event:`` field,
blank-line dispatch, EOF flush); ``decode_frame`` maps one frame to a
typed event; ``collect_events`` consumes an ``httpx`` ``iter_lines()``
stream into a ``SseStreamResult``. Terminal conditions per the map: the
``[DONE]`` sentinel, flavor B ``event=done``/``is_final=true``, and
in-band error frames. A stream ending without any terminal is reported
as ``terminal=None`` so callers can flag the protocol violation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

DONE_SENTINEL: Final[str] = "[DONE]"
"""Literal sentinel frame that terminates every documented SSE stream."""


class SseParseError(RuntimeError):
    """A data frame was neither the ``[DONE]`` sentinel nor a JSON object."""

    def __init__(self, raw_data: str) -> None:
        super().__init__(f"malformed SSE data frame (not JSON): {raw_data!r}")
        self.raw_data = raw_data


@dataclass(frozen=True)
class SseFrame:
    """One dispatched SSE frame: data lines joined, optional event field."""

    data: str
    event_name: str | None = None


@dataclass(frozen=True)
class SseItem:
    """Flavor A raw item payload (no ``event`` discriminator)."""

    payload: dict[str, object]


@dataclass(frozen=True)
class SseProgress:
    """Flavor B ``event=progress`` envelope."""

    payload: dict[str, object]


@dataclass(frozen=True)
class SseResult:
    """Flavor B ``event=result`` envelope."""

    payload: dict[str, object]


@dataclass(frozen=True)
class SseDone:
    """Flavor B ``event=done`` envelope (terminal)."""

    payload: dict[str, object]


@dataclass(frozen=True)
class SseErrorEvent:
    """In-band terminal error — flavor A ``{"error", "code"}`` or flavor B
    ``event=error``."""

    message: str
    code: str | None
    payload: dict[str, object]


@dataclass(frozen=True)
class SseSentinel:
    """The literal ``[DONE]`` sentinel frame (terminal)."""

    pass


SseItemEvent = SseItem | SseProgress | SseResult
"""Non-terminal collected events."""
SseTerminal = SseDone | SseErrorEvent | SseSentinel
"""Terminal conditions per the API map (§6)."""
SseEvent = SseItemEvent | SseTerminal


def parse_frames(lines: Iterable[str]) -> Iterator[SseFrame]:
    """Yield SSE frames from raw text lines (e.g. ``Response.iter_lines()``).

    Follows the SSE line semantics: ``:``-prefixed comments are skipped
    (keep-alive), consecutive ``data:`` lines of one event join with ``\\n``,
    a blank line dispatches, and a trailing frame at EOF is flushed for
    servers that close without a final blank line. ``event:`` field lines
    are captured (tolerated, never required — the map's streams are
    data-only); ``id:``/``retry:``/unknown fields are ignored.
    """
    data_lines: list[str] = []
    event_name: str | None = None
    for raw_line in lines:
        line = raw_line.removesuffix("\r")
        if line.startswith(":"):
            continue
        if not line:
            if data_lines or event_name is not None:
                yield SseFrame(data="\n".join(data_lines), event_name=event_name)
                data_lines = []
                event_name = None
            continue
        field, _sep, value = line.partition(":")
        value = value.removeprefix(" ")
        if field == "data":
            data_lines.append(value)
        elif field == "event":
            event_name = value
    if data_lines or event_name is not None:
        yield SseFrame(data="\n".join(data_lines), event_name=event_name)


def decode_frame(frame: SseFrame) -> SseEvent:
    """Decode one frame into a typed event per the map's §6 contract.

    ``[DONE]`` → ``SseSentinel``; ``{"error": <str>, "code": <str>}`` or
    ``event=error`` → ``SseErrorEvent``; in-band ``event`` key → flavor B
    envelopes; anything else → ``SseItem``. Malformed (non-JSON, non-object)
    data raises ``SseParseError`` — fail-fast: a malformed frame means the
    server's stream protocol drifted.
    """
    if frame.data == DONE_SENTINEL:
        return SseSentinel()
    try:
        payload: object = json.loads(frame.data)
    except json.JSONDecodeError as exc:
        raise SseParseError(frame.data) from exc
    if not isinstance(payload, dict):
        raise SseParseError(frame.data)
    typed: dict[str, object] = payload
    error = typed.get("error")
    code = typed.get("code")
    if isinstance(error, str) and isinstance(code, str):
        return SseErrorEvent(message=error, code=code, payload=typed)
    if typed.get("event") == "error":
        # Flavor B's discriminator is authoritative; render non-string
        # error payloads instead of dropping the terminal evidence.
        message = error if isinstance(error, str) else json.dumps(error)
        return SseErrorEvent(
            message=message,
            code=code if isinstance(code, str) else None,
            payload=typed,
        )
    match typed.get("event"):
        case "progress":
            return SseProgress(payload=typed)
        case "result":
            return SseResult(payload=typed)
        case "done":
            return SseDone(payload=typed)
        case _:
            return SseItem(payload=typed)


@dataclass(frozen=True)
class SseStreamResult:
    """Collected non-terminal events plus the terminal that ended the stream.

    ``terminal=None`` means the stream ended without a documented terminal —
    a protocol violation callers must surface, never silently accept.
    """

    events: tuple[SseItemEvent, ...]
    terminal: SseTerminal | None


def collect_events(lines: Iterable[str]) -> SseStreamResult:
    """Consume ``httpx`` ``iter_lines()`` output into typed events.

    Stops at the first terminal (``[DONE]``, ``event=done``, in-band
    error); any remaining lines are discarded. Malformed frames raise
    ``SseParseError`` immediately.
    """
    events: list[SseItemEvent] = []
    for frame in parse_frames(lines):
        event = decode_frame(frame)
        if isinstance(event, SseItemEvent):
            events.append(event)
            continue
        return SseStreamResult(events=tuple(events), terminal=event)
    return SseStreamResult(events=tuple(events), terminal=None)
