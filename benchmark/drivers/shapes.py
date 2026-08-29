"""Capability invocation shapes — REST-JSON, SSE-collect, poll-until-done.

The three documented invocation shapes (api-surface.md §7) as shape
helpers over :class:`benchmark.drivers.base.CapabilityContext`
(RULE-04 split: ``base.py`` stays contract-only):

- :func:`invoke_rest` — one authenticated request, parsed JSON body.
- :func:`invoke_sse` / :func:`collect_sse_within_deadline` — collect the
  stream to terminal state under a TOTAL deadline (T3 rider: a
  keep-alive-forever stream must never hang the runner). The deadline
  guard checks a monotonic clock on every incoming line, so keep-alive
  traffic cannot starve it; total silence (no lines at all) is covered
  by the client's httpx read timeout. Deadlines come from
  ``ctx.config.sse_deadline_seconds``, wired by the runner.
- :func:`poll_until_done` — repeat a request until a predicate fires,
  never sleeping past the timeout; timings from ``ctx.config``.

Every completed exchange is appended to ``ctx.events`` as a sanitized
``IngestEvent`` (``benchmark.ingest_events``). A deadlined SSE stream is
recorded too (exchange opened, never terminated) before the error
propagates; ``ApiError`` transport/HTTP failures propagate unrecorded —
the driver's ERROR ``CapabilityResult`` reason carries them.

Errors are fail-fast exceptions (``SseDeadlineError``,
``PollTimeoutError``); the driver decides whether to convert them into
an ERROR ``CapabilityResult`` or to propagate (runner policy, Task 15).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from benchmark.ingest_events import record
from benchmark.sse import SseStreamResult, collect_events

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

    from benchmark.drivers.base import CapabilityContext
    from benchmark.sse import SseTerminal


# ---------------------------------------------------------------------------
# Shared: sanitized recording into the run sink
# ---------------------------------------------------------------------------


def _record(
    ctx: CapabilityContext,
    *,
    step: str,
    chapter_stem: str | None,
    method: str,
    path: str,
    status: int,
    started: float,
    request_body: object | None,
    response_body: object,
) -> None:
    record(
        ctx.events,
        step=step,
        chapter_stem=chapter_stem,
        method=method,
        path=path,
        status=status,
        started=started,
        request_body=request_body,
        response_body=response_body,
    )


# ---------------------------------------------------------------------------
# Shape 1: REST-JSON (single request)
# ---------------------------------------------------------------------------


def invoke_rest(
    ctx: CapabilityContext,
    *,
    step: str,
    method: str,
    path: str,
    json_body: object | None = None,
    params: Mapping[str, str] | None = None,
    chapter_stem: str | None = None,
) -> object:
    """One authenticated request; returns the parsed JSON body.

    Non-2xx raises ``ApiError`` (client contract); the completed exchange
    is recorded into ``ctx.events`` (sanitized) before returning.
    """
    started = time.perf_counter()
    response = ctx.client.request(method, path, json=json_body, params=params)
    body: object = response.json() if response.content else None
    _record(
        ctx,
        step=step,
        chapter_stem=chapter_stem,
        method=method,
        path=path,
        status=response.status_code,
        started=started,
        request_body=json_body,
        response_body=body,
    )
    return body


# ---------------------------------------------------------------------------
# Shape 2: SSE-collect (stream to terminal state, total deadline)
# ---------------------------------------------------------------------------


class SseDeadlineError(RuntimeError):
    """The SSE stream did not reach a terminal state within the deadline."""

    def __init__(self, *, deadline_seconds: float, elapsed_seconds: float) -> None:
        super().__init__(
            f"SSE stream exceeded its total deadline: {elapsed_seconds:.3f}s elapsed "
            f"(deadline {deadline_seconds:.3f}s) — stream never reached a terminal state"
        )
        self.deadline_seconds = deadline_seconds
        self.elapsed_seconds = elapsed_seconds


def collect_sse_within_deadline(
    lines: Iterable[str],
    *,
    deadline_seconds: float,
) -> SseStreamResult:
    """Collect SSE events with a TOTAL wall-clock deadline (T3 rider).

    The deadline guard sits between the raw line source and the parser:
    every incoming line first passes a monotonic-clock check, so a
    keep-alive-forever server (infinite comment frames) deterministically
    raises ``SseDeadlineError`` instead of hanging the runner. A server
    that goes fully silent never feeds the guard — that hang mode is
    covered by the client's httpx read timeout.
    """
    deadline = time.monotonic() + deadline_seconds
    return collect_events(_deadline_guard(lines, deadline, deadline_seconds))


def _deadline_guard(
    lines: Iterable[str],
    deadline: float,
    deadline_seconds: float,
) -> Iterator[str]:
    started = deadline - deadline_seconds
    for line in lines:
        now = time.monotonic()
        if now >= deadline:
            raise SseDeadlineError(deadline_seconds=deadline_seconds, elapsed_seconds=now - started)
        yield line


def invoke_sse(
    ctx: CapabilityContext,
    *,
    step: str,
    path: str,
    json_body: object | None = None,
    chapter_stem: str | None = None,
) -> SseStreamResult:
    """POST the SSE endpoint and collect to terminal state under the deadline.

    Every documented SSE endpoint is POST (map §7); pre-stream failures
    raise ``ApiError`` (unrecorded), a deadline breach is recorded as
    deadline evidence and re-raised as ``SseDeadlineError``.
    """
    started = time.perf_counter()
    try:
        with ctx.client.stream("POST", path, json=json_body) as lines:
            result = collect_sse_within_deadline(
                lines, deadline_seconds=ctx.config.sse_deadline_seconds
            )
    except SseDeadlineError:
        _record(
            ctx,
            step=step,
            chapter_stem=chapter_stem,
            method="POST",
            path=path,
            status=200,
            started=started,
            request_body=json_body,
            response_body={"event_count": None, "terminal": "deadline-exceeded"},
        )
        raise
    _record(
        ctx,
        step=step,
        chapter_stem=chapter_stem,
        method="POST",
        path=path,
        status=200,
        started=started,
        request_body=json_body,
        response_body={"event_count": len(result.events), "terminal": _label(result.terminal)},
    )
    return result


def _label(terminal: SseTerminal | None) -> str:
    match terminal:
        case None:
            return "none"
        case _:
            return type(terminal).__name__


# ---------------------------------------------------------------------------
# Shape 3: poll-until-done
# ---------------------------------------------------------------------------


class PollTimeoutError(RuntimeError):
    """The poll predicate never fired within ``poll_timeout_seconds``."""

    def __init__(self, *, path: str, attempts: int, timeout_seconds: float) -> None:
        super().__init__(
            f"poll of {path} timed out after {attempts} attempts (timeout {timeout_seconds:.3f}s)"
        )
        self.path = path
        self.attempts = attempts
        self.timeout_seconds = timeout_seconds


def poll_until_done(
    ctx: CapabilityContext,
    *,
    step: str,
    method: str,
    path: str,
    is_done: Callable[[object], bool],
    json_body: object | None = None,
    params: Mapping[str, str] | None = None,
    chapter_stem: str | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> object:
    """Poll a GET/POST endpoint until ``is_done(body)`` fires; every poll
    exchange is recorded. Never sleeps past the timeout deadline; raises
    ``PollTimeoutError`` carrying the attempt count."""
    deadline = time.monotonic() + ctx.config.poll_timeout_seconds
    attempts = 0
    while True:
        body = invoke_rest(
            ctx,
            step=step,
            method=method,
            path=path,
            json_body=json_body,
            params=params,
            chapter_stem=chapter_stem,
        )
        attempts += 1
        if is_done(body):
            return body
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PollTimeoutError(
                path=path, attempts=attempts, timeout_seconds=ctx.config.poll_timeout_seconds
            )
        sleeper(min(ctx.config.poll_interval_seconds, remaining))
